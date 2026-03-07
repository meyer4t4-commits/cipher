import Foundation
import AVFoundation
import Speech

// MARK: - Voice Service

@Observable
class VoiceService {
    static let shared = VoiceService()

    var isListening = false
    var isAuthorized = false
    var transcription = ""
    var audioLevel: Float = 0.0

    // Voice response playback
    var isPlayingResponse = false
    var selectedVoiceId: String {
        get {
            UserDefaults.standard.string(forKey: "selected_voice_id") ?? "default"
        }
        set {
            UserDefaults.standard.set(newValue, forKey: "selected_voice_id")
        }
    }

    var voiceResponseEnabled: Bool {
        get {
            UserDefaults.standard.object(forKey: "voice_response_enabled") as? Bool ?? false
        }
        set {
            UserDefaults.standard.set(newValue, forKey: "voice_response_enabled")
        }
    }

    @ObservationIgnored var audioEngine: AVAudioEngine?
    @ObservationIgnored var recognitionTask: SFSpeechRecognitionTask?
    @ObservationIgnored var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    @ObservationIgnored let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))

    @ObservationIgnored var audioPlayer: AVAudioPlayer?
    @ObservationIgnored var playerDelegate: AudioPlayerDelegateHandler?

    init() {}

    // MARK: - Authorization

    func requestAuthorization() async -> Bool {
        let speechStatus = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status)
            }
        }

        guard speechStatus == .authorized else {
            isAuthorized = false
            return false
        }

        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.record, mode: .measurement, options: .duckOthers)
            try session.setActive(true, options: .notifyOthersOnDeactivation)
        } catch {
            isAuthorized = false
            return false
        }

        isAuthorized = true
        return true
    }

    // MARK: - Start Listening

    @MainActor
    func startListening() async {
        guard isAuthorized, !isListening else { return }

        transcription = ""
        audioEngine = AVAudioEngine()

        guard let audioEngine = audioEngine,
              let recognizer = speechRecognizer,
              recognizer.isAvailable else { return }

        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let request = recognitionRequest else { return }

        request.shouldReportPartialResults = true
        request.addsPunctuation = true

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)

            let channelData = buffer.floatChannelData?[0]
            let frameLength = Int(buffer.frameLength)
            if let data = channelData {
                var sum: Float = 0
                for i in 0..<frameLength {
                    sum += abs(data[i])
                }
                let avgPower = sum / Float(frameLength)
                DispatchQueue.main.async {
                    self?.audioLevel = min(avgPower * 10, 1.0)
                }
            }
        }

        recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self = self else { return }

            if let result = result {
                DispatchQueue.main.async {
                    self.transcription = result.bestTranscription.formattedString
                }
            }

            if error != nil || (result?.isFinal ?? false) {
                DispatchQueue.main.async {
                    self.stopListening()
                }
            }
        }

        do {
            audioEngine.prepare()
            try audioEngine.start()
            isListening = true
        } catch {
            stopListening()
        }
    }

    // MARK: - Stop Listening

    @MainActor
    func stopListening() {
        audioEngine?.stop()
        audioEngine?.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = nil
        audioEngine = nil
        isListening = false
        audioLevel = 0.0
    }

    // MARK: - Text to Speech (Legacy)

    func speak(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        utterance.rate = 0.52
        utterance.pitchMultiplier = 1.0
        utterance.volume = 0.9

        let synthesizer = AVSpeechSynthesizer()
        synthesizer.speak(utterance)
    }

    // MARK: - Voice Synthesis (Orchid TTS)

    @MainActor
    func synthesizeSpeech(_ text: String) async -> Data? {
        do {
            let audioData = try await OrchidAPI.shared.synthesizeSpeech(
                text: text,
                voiceId: selectedVoiceId
            )
            return audioData
        } catch {
            print("Speech synthesis error: \(error)")
            return nil
        }
    }

    // MARK: - Voice Playback

    @MainActor
    func playVoiceResponse(audioData: Data) {
        guard !audioData.isEmpty else { return }

        do {
            let audioSession = AVAudioSession.sharedInstance()
            try audioSession.setCategory(.playback, mode: .spokenAudio, options: .duckOthers)
            try audioSession.setActive(true)

            audioPlayer = try AVAudioPlayer(data: audioData, fileTypeHint: "public.mp3")
            playerDelegate = AudioPlayerDelegateHandler { [weak self] in
                DispatchQueue.main.async {
                    self?.isPlayingResponse = false
                }
            }
            audioPlayer?.delegate = playerDelegate
            isPlayingResponse = true
            audioPlayer?.play()
        } catch {
            print("Audio playback error: \(error)")
            isPlayingResponse = false
        }
    }

    @MainActor
    func stopPlayback() {
        audioPlayer?.stop()
        isPlayingResponse = false
    }
}

// MARK: - Audio Player Delegate Handler

class AudioPlayerDelegateHandler: NSObject, AVAudioPlayerDelegate {
    let onFinish: () -> Void

    init(onFinish: @escaping () -> Void) {
        self.onFinish = onFinish
        super.init()
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        onFinish()
    }

    func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
        onFinish()
    }
}
