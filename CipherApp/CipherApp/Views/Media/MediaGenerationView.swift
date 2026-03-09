import SwiftUI
import PhotosUI

// MARK: - Media Tab Enum

enum MediaTab: String, CaseIterable {
    case image = "Image"
    case video = "Video"
}

// MARK: - Media View Model

@Observable
class MediaViewModel {
    // Tab selection
    var selectedTab: MediaTab = .image

    // Image parameters
    var imagePrompt: String = ""
    var imageSize: String = "1024x1024"
    var imageQuality: String = "standard"
    var imageStyle: String = "natural"

    // Video parameters
    var videoPrompt: String = ""
    var videoDuration: Int = 5
    var aspectRatio: String = "16:9"
    var isChainVideoEnabled: Bool = false
    var chainVideoScenes: [String] = []

    // Loading and result state
    var isGenerating: Bool = false
    var result: [String: AnyCodable]? = nil
    var errorMessage: String? = nil

    private let api = CipherAPI.shared

    // MARK: - Image Generation

    func generateImage() async {
        guard !imagePrompt.trimmingCharacters(in: .whitespaces).isEmpty else {
            errorMessage = "Please enter a prompt"
            return
        }

        isGenerating = true
        errorMessage = nil
        result = nil

        do {
            let response = try await api.generateImage(
                prompt: imagePrompt,
                size: imageSize,
                quality: imageQuality,
                style: imageStyle
            )
            self.result = response
        } catch {
            self.errorMessage = error.localizedDescription
        }

        isGenerating = false
    }

    // MARK: - Video Generation

    func generateVideo() async {
        if isChainVideoEnabled {
            await generateChainVideo()
        } else {
            await generateSingleVideo()
        }
    }

    private func generateSingleVideo() async {
        guard !videoPrompt.trimmingCharacters(in: .whitespaces).isEmpty else {
            errorMessage = "Please enter a prompt"
            return
        }

        isGenerating = true
        errorMessage = nil
        result = nil

        do {
            let response = try await api.generateVideo(
                prompt: videoPrompt,
                duration: videoDuration,
                aspectRatio: aspectRatio
            )
            self.result = response
        } catch {
            self.errorMessage = error.localizedDescription
        }

        isGenerating = false
    }

    private func generateChainVideo() async {
        var prompts = [videoPrompt]
        prompts.append(contentsOf: chainVideoScenes.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty })

        guard !prompts.isEmpty && prompts.contains(where: { !$0.trimmingCharacters(in: .whitespaces).isEmpty }) else {
            errorMessage = "Please enter at least one scene"
            return
        }

        isGenerating = true
        errorMessage = nil
        result = nil

        do {
            let response = try await api.chainVideo(
                scenes: prompts,
                durationPerClip: videoDuration
            )
            self.result = response
        } catch {
            self.errorMessage = error.localizedDescription
        }

        isGenerating = false
    }

    // MARK: - Chain Video Management

    func addScene() {
        chainVideoScenes.append("")
    }

    func removeScene(at index: Int) {
        guard index < chainVideoScenes.count else { return }
        chainVideoScenes.remove(at: index)
    }
}

// MARK: - Media Generation View

struct MediaGenerationView: View {
    @State private var viewModel = MediaViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Header with segmented picker
                VStack(spacing: Spacing.lg) {
                    Text("Generate Media")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundColor(CipherTheme.textPrimary)
                        .frame(maxWidth: .infinity, alignment: .leading)

                    Picker("Media Type", selection: $viewModel.selectedTab) {
                        ForEach(MediaTab.allCases, id: \.self) { tab in
                            Text(tab.rawValue).tag(tab)
                        }
                    }
                    .pickerStyle(.segmented)
                    .colorMultiply(CipherTheme.accent)
                }
                .padding(Spacing.lg)
                .background(CipherTheme.background)
                .border(width: 0.5, edges: [.bottom], color: CipherTheme.border)

                // Content based on selected tab
                ScrollView {
                    VStack(spacing: Spacing.lg) {
                        if viewModel.selectedTab == .image {
                            imageGenerationSection
                        } else {
                            videoGenerationSection
                        }

                        // Results section
                        if viewModel.isGenerating {
                            progressSection
                        } else if viewModel.result != nil {
                            resultSection
                        }

                        // Error message
                        if let error = viewModel.errorMessage {
                            errorBanner(error)
                        }

                        Spacer(minLength: Spacing.xl)
                    }
                    .padding(Spacing.lg)
                }
            }
            .background(CipherTheme.background)
        }
    }

    // MARK: - Image Generation Section

    private var imageGenerationSection: some View {
        VStack(spacing: Spacing.md) {
            // Prompt input
            VStack(alignment: .leading, spacing: Spacing.sm) {
                Text("Prompt")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.textSecondary)

                TextEditor(text: $viewModel.imagePrompt)
                    .font(.system(size: 16))
                    .foregroundColor(CipherTheme.textPrimary)
                    .padding(Spacing.md)
                    .frame(minHeight: 80)
                    .background(CipherTheme.surfaceElevated)
                    .cornerRadius(CornerRadius.md)
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.md)
                            .stroke(CipherTheme.border, lineWidth: 0.5)
                    )
            }

            // Size picker
            VStack(alignment: .leading, spacing: Spacing.sm) {
                Text("Size")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.textSecondary)

                Picker("Size", selection: $viewModel.imageSize) {
                    Text("1024×1024").tag("1024x1024")
                    Text("1792×1024").tag("1792x1024")
                    Text("1024×1792").tag("1024x1792")
                }
                .pickerStyle(.menu)
                .frame(maxWidth: .infinity, alignment: .leading)
                .font(.system(size: 16))
                .foregroundColor(CipherTheme.textPrimary)
                .padding(.horizontal, Spacing.md)
                .padding(.vertical, Spacing.sm)
                .background(CipherTheme.surfaceElevated)
                .cornerRadius(CornerRadius.md)
            }

            // Quality and Style pickers
            HStack(spacing: Spacing.md) {
                VStack(alignment: .leading, spacing: Spacing.sm) {
                    Text("Quality")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(CipherTheme.textSecondary)

                    Picker("Quality", selection: $viewModel.imageQuality) {
                        Text("Standard").tag("standard")
                        Text("HD").tag("hd")
                    }
                    .pickerStyle(.menu)
                    .font(.system(size: 16))
                    .foregroundColor(CipherTheme.textPrimary)
                    .padding(.horizontal, Spacing.md)
                    .padding(.vertical, Spacing.sm)
                    .background(CipherTheme.surfaceElevated)
                    .cornerRadius(CornerRadius.md)
                }

                VStack(alignment: .leading, spacing: Spacing.sm) {
                    Text("Style")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(CipherTheme.textSecondary)

                    Picker("Style", selection: $viewModel.imageStyle) {
                        Text("Vivid").tag("vivid")
                        Text("Natural").tag("natural")
                    }
                    .pickerStyle(.menu)
                    .font(.system(size: 16))
                    .foregroundColor(CipherTheme.textPrimary)
                    .padding(.horizontal, Spacing.md)
                    .padding(.vertical, Spacing.sm)
                    .background(CipherTheme.surfaceElevated)
                    .cornerRadius(CornerRadius.md)
                }
            }

            // Generate button
            Button(action: {
                Task {
                    await viewModel.generateImage()
                }
            }) {
                Text("Generate Image")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(CipherTheme.textOnAccent)
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .background(CipherTheme.accentGradient)
                    .cornerRadius(CornerRadius.lg)
            }
            .disabled(viewModel.isGenerating)
        }
    }

    // MARK: - Video Generation Section

    private var videoGenerationSection: some View {
        VStack(spacing: Spacing.md) {
            // Prompt input
            VStack(alignment: .leading, spacing: Spacing.sm) {
                Text("Prompt")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.textSecondary)

                TextEditor(text: $viewModel.videoPrompt)
                    .font(.system(size: 16))
                    .foregroundColor(CipherTheme.textPrimary)
                    .padding(Spacing.md)
                    .frame(minHeight: 80)
                    .background(CipherTheme.surfaceElevated)
                    .cornerRadius(CornerRadius.md)
                    .overlay(
                        RoundedRectangle(cornerRadius: CornerRadius.md)
                            .stroke(CipherTheme.border, lineWidth: 0.5)
                    )
            }

            // Duration and Aspect Ratio pickers
            HStack(spacing: Spacing.md) {
                VStack(alignment: .leading, spacing: Spacing.sm) {
                    Text("Duration")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(CipherTheme.textSecondary)

                    Picker("Duration", selection: $viewModel.videoDuration) {
                        Text("5 seconds").tag(5)
                        Text("10 seconds").tag(10)
                    }
                    .pickerStyle(.menu)
                    .font(.system(size: 16))
                    .foregroundColor(CipherTheme.textPrimary)
                    .padding(.horizontal, Spacing.md)
                    .padding(.vertical, Spacing.sm)
                    .background(CipherTheme.surfaceElevated)
                    .cornerRadius(CornerRadius.md)
                }

                VStack(alignment: .leading, spacing: Spacing.sm) {
                    Text("Aspect Ratio")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundColor(CipherTheme.textSecondary)

                    Picker("Aspect Ratio", selection: $viewModel.aspectRatio) {
                        Text("16:9").tag("16:9")
                        Text("9:16").tag("9:16")
                        Text("1:1").tag("1:1")
                    }
                    .pickerStyle(.menu)
                    .font(.system(size: 16))
                    .foregroundColor(CipherTheme.textPrimary)
                    .padding(.horizontal, Spacing.md)
                    .padding(.vertical, Spacing.sm)
                    .background(CipherTheme.surfaceElevated)
                    .cornerRadius(CornerRadius.md)
                }
            }

            // Chain video toggle
            HStack {
                Toggle(isOn: $viewModel.isChainVideoEnabled) {
                    VStack(alignment: .leading, spacing: Spacing.xs) {
                        Text("Chain Video")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundColor(CipherTheme.textPrimary)

                        Text("Create longer videos by combining multiple scenes")
                            .font(.system(size: 12))
                            .foregroundColor(CipherTheme.textSecondary)
                    }
                }
                .toggleStyle(.switch)
                Spacer()
            }
            .padding(Spacing.md)
            .background(CipherTheme.surfaceElevated)
            .cornerRadius(CornerRadius.md)

            // Chain video scenes (shown when enabled)
            if viewModel.isChainVideoEnabled {
                chainVideoScenesEditor
            }

            // Generate button
            Button(action: {
                Task {
                    await viewModel.generateVideo()
                }
            }) {
                Text("Generate Video")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(CipherTheme.textOnAccent)
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .background(CipherTheme.accentGradient)
                    .cornerRadius(CornerRadius.lg)
            }
            .disabled(viewModel.isGenerating)
        }
    }

    // MARK: - Chain Video Scenes Editor

    private var chainVideoScenesEditor: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Additional Scenes")
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(CipherTheme.textSecondary)

            ForEach(Array(viewModel.chainVideoScenes.enumerated()), id: \.offset) { index, scene in
                HStack(spacing: Spacing.sm) {
                    TextField("Scene \(index + 2)", text: $viewModel.chainVideoScenes[index])
                        .font(.system(size: 16))
                        .foregroundColor(CipherTheme.textPrimary)
                        .padding(.horizontal, Spacing.md)
                        .padding(.vertical, Spacing.sm)
                        .background(CipherTheme.surfaceElevated)
                        .cornerRadius(CornerRadius.md)
                        .overlay(
                            RoundedRectangle(cornerRadius: CornerRadius.md)
                                .stroke(CipherTheme.border, lineWidth: 0.5)
                        )

                    Button(action: {
                        viewModel.removeScene(at: index)
                    }) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 20))
                            .foregroundColor(CipherTheme.error)
                    }
                }
            }

            Button(action: {
                viewModel.addScene()
            }) {
                HStack {
                    Image(systemName: "plus.circle.fill")
                    Text("Add Scene")
                }
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(CipherTheme.accent)
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(Spacing.md)
                .background(CipherTheme.surfaceElevated)
                .cornerRadius(CornerRadius.md)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.md)
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
            }
        }
    }

    // MARK: - Progress Section

    private var progressSection: some View {
        VStack(spacing: Spacing.lg) {
            SpinningCipherLogo(size: 48, spinning: true)

            VStack(spacing: Spacing.sm) {
                Text(viewModel.selectedTab == .image ? "Generating image" : "Generating video")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text(viewModel.selectedTab == .image ? "This may take a minute" : "This may take several minutes")
                    .font(.system(size: 14))
                    .foregroundColor(CipherTheme.textSecondary)
            }
        }
        .padding(Spacing.lg)
        .background(CipherTheme.surfaceElevated)
        .cornerRadius(CornerRadius.md)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.border, lineWidth: 0.5)
        )
    }

    // MARK: - Result Section

    private var resultSection: some View {
        VStack(spacing: Spacing.lg) {
            if viewModel.selectedTab == .image {
                imageResultSection
            } else {
                videoResultSection
            }
        }
    }

    private var imageResultSection: some View {
        VStack(spacing: Spacing.md) {
            if let imageUrl = viewModel.result?["image_url"]?.stringValue ?? viewModel.result?["url"]?.stringValue {
                AsyncImage(url: URL(string: imageUrl)) { phase in
                    switch phase {
                    case .empty:
                        SpinningCipherLogo(size: 40, spinning: true)
                            .frame(maxWidth: .infinity)
                            .frame(height: 300)
                            .background(CipherTheme.surfaceElevated)
                            .cornerRadius(CornerRadius.md)

                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFit()
                            .cornerRadius(CornerRadius.md)

                    case .failure:
                        VStack(spacing: Spacing.sm) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.system(size: 24))
                                .foregroundColor(CipherTheme.error)

                            Text("Failed to load image")
                                .foregroundColor(CipherTheme.textSecondary)
                        }
                        .frame(maxWidth: .infinity)
                        .frame(height: 200)
                        .background(CipherTheme.surfaceElevated)
                        .cornerRadius(CornerRadius.md)

                    @unknown default:
                        EmptyView()
                    }
                }

                // Save to Photos button
                Button(action: {
                    // TODO: Implement saving to Photos
                }) {
                    HStack {
                        Image(systemName: "photo")
                        Text("Save to Photos")
                    }
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(CipherTheme.textOnAccent)
                    .frame(maxWidth: .infinity)
                    .padding(Spacing.md)
                    .background(CipherTheme.accentGradient)
                    .cornerRadius(CornerRadius.md)
                }
            }

            if let filename = viewModel.result?["filename"]?.stringValue {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(CipherTheme.success)
                    Text("Saved as: \(filename)")
                        .font(.system(size: 14))
                        .foregroundColor(CipherTheme.textSecondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(Spacing.md)
                .background(CipherTheme.success.opacity(0.1))
                .cornerRadius(CornerRadius.md)
            }
        }
    }

    private var videoResultSection: some View {
        VStack(spacing: Spacing.md) {
            if let videoUrl = viewModel.result?["video_url"]?.stringValue ?? viewModel.result?["url"]?.stringValue {
                VStack(spacing: Spacing.md) {
                    Image(systemName: "video.fill")
                        .font(.system(size: 40))
                        .foregroundColor(CipherTheme.accent)

                    Text("Video Generated")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundColor(CipherTheme.textPrimary)

                    if let duration = viewModel.result?["duration_seconds"]?.intValue {
                        Text("Duration: \(duration) seconds")
                            .font(.system(size: 14))
                            .foregroundColor(CipherTheme.textSecondary)
                    }

                    Button(action: {
                        if let url = URL(string: videoUrl) {
                            UIApplication.shared.open(url)
                        }
                    }) {
                        HStack {
                            Image(systemName: "safari")
                            Text("Open in Browser")
                        }
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(CipherTheme.textOnAccent)
                        .frame(maxWidth: .infinity)
                        .padding(Spacing.md)
                        .background(CipherTheme.accentGradient)
                        .cornerRadius(CornerRadius.md)
                    }
                }
                .padding(Spacing.lg)
                .background(CipherTheme.surfaceElevated)
                .cornerRadius(CornerRadius.md)
                .overlay(
                    RoundedRectangle(cornerRadius: CornerRadius.md)
                        .stroke(CipherTheme.border, lineWidth: 0.5)
                )
            }

            if let filename = viewModel.result?["filename"]?.stringValue {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(CipherTheme.success)
                    Text("Saved as: \(filename)")
                        .font(.system(size: 14))
                        .foregroundColor(CipherTheme.textSecondary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(Spacing.md)
                .background(CipherTheme.success.opacity(0.1))
                .cornerRadius(CornerRadius.md)
            }
        }
    }

    // MARK: - Error Banner

    private func errorBanner(_ message: String) -> some View {
        HStack(spacing: Spacing.sm) {
            Image(systemName: "exclamationmark.circle.fill")
                .foregroundColor(CipherTheme.error)

            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text("Error")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(CipherTheme.textPrimary)

                Text(message)
                    .font(.system(size: 13))
                    .foregroundColor(CipherTheme.textSecondary)
                    .lineLimit(3)
            }

            Spacer()
        }
        .padding(Spacing.md)
        .background(CipherTheme.error.opacity(0.1))
        .cornerRadius(CornerRadius.md)
        .overlay(
            RoundedRectangle(cornerRadius: CornerRadius.md)
                .stroke(CipherTheme.error.opacity(0.3), lineWidth: 0.5)
        )
    }
}

// MARK: - Helper View Extension

extension View {
    func border(width: CGFloat, edges: [Edge], color: Color) -> some View {
        overlay(alignment: .top) {
            if edges.contains(.top) {
                Rectangle()
                    .fill(color)
                    .frame(height: width)
            }
        }
        .overlay(alignment: .bottom) {
            if edges.contains(.bottom) {
                Rectangle()
                    .fill(color)
                    .frame(height: width)
            }
        }
        .overlay(alignment: .leading) {
            if edges.contains(.leading) {
                Rectangle()
                    .fill(color)
                    .frame(width: width)
            }
        }
        .overlay(alignment: .trailing) {
            if edges.contains(.trailing) {
                Rectangle()
                    .fill(color)
                    .frame(width: width)
            }
        }
    }
}

// AnyCodable is defined in AgentModels.swift — no duplicate needed here

// MARK: - CipherAPI Extension

extension CipherAPI {
    func generateImage(
        prompt: String,
        size: String,
        quality: String,
        style: String
    ) async throws -> [String: AnyCodable] {
        let endpoint = serverURL + "/api/v1/media/generate-image"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let body: [String: Any] = [
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "style": style,
        ]

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(httpResponse.statusCode, "Failed to generate image")
        }

        let jsonObject = try JSONSerialization.jsonObject(with: data)
        if let dict = jsonObject as? [String: Any] {
            return dict.mapValues { AnyCodable($0) }
        }

        throw APIError.decodingError
    }

    func generateVideo(
        prompt: String,
        duration: Int,
        aspectRatio: String
    ) async throws -> [String: AnyCodable] {
        let endpoint = serverURL + "/api/v1/media/generate-video"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let body: [String: Any] = [
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": aspectRatio,
        ]

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(httpResponse.statusCode, "Failed to generate video")
        }

        let jsonObject = try JSONSerialization.jsonObject(with: data)
        if let dict = jsonObject as? [String: Any] {
            return dict.mapValues { AnyCodable($0) }
        }

        throw APIError.decodingError
    }

    func chainVideo(
        scenes: [String],
        durationPerClip: Int
    ) async throws -> [String: AnyCodable] {
        let endpoint = serverURL + "/api/v1/media/chain-video"
        guard let url = URL(string: endpoint) else {
            throw APIError.invalidURL
        }

        let body: [String: Any] = [
            "scenes": scenes,
            "duration_per_clip": durationPerClip,
        ]

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(httpResponse.statusCode, "Failed to chain video")
        }

        let jsonObject = try JSONSerialization.jsonObject(with: data)
        if let dict = jsonObject as? [String: Any] {
            return dict.mapValues { AnyCodable($0) }
        }

        throw APIError.decodingError
    }
}

// MARK: - Preview

#Preview {
    MediaGenerationView()
}
