# Cipher Voice Scraping Mission

## Objective
Find and collect high-quality audio reference samples for 10 education platform voice characters. These samples will be used as references for ElevenLabs Voice Design API to generate matching synthetic voices. Store all results in my project folder.

## What I Need Per Voice
For each character below, find **3-5 audio/video clips** from YouTube, podcasts, interviews, or audiobooks that match the described voice profile. Save a structured JSON file with:
- Character name
- Target voice profile (age, gender, accent, energy)
- URLs to reference clips (with timestamps if possible)
- Why each clip matches the character
- Any ElevenLabs Voice Design API prompt refinements based on what you find

## The 10 Voices to Source

### 1. Nonna Maria — Italian Language
- **Target:** Older Italian female, warm and nurturing, slight Italian accent, grandmother energy
- **Search for:** Italian grandmothers cooking on YouTube, Italian language teachers with warm delivery, Lidia Bastianich-style speakers
- **Design prompt:** "Older Italian female, warm and nurturing, slight Italian accent, the voice of a grandmother who insists you eat more, patient but animated when passionate about food or family"

### 2. Teacher Lin — Mandarin Chinese
- **Target:** Young Chinese female, clear and patient, precise tonal pronunciation, calm and encouraging
- **Search for:** Popular Mandarin teachers on YouTube (ChinesePod, Yoyo Chinese), clear female Mandarin instructors
- **Design prompt:** "Young Chinese female, clear and patient, precise tonal pronunciation, calm and encouraging, modern professional, switches naturally between Mandarin and English"

### 3. The Sage — Philosophy
- **Target:** Mature male, deep contemplative voice, measured pacing, British-influenced, Alan Watts energy
- **Search for:** Alan Watts lectures, philosophy podcast hosts with deep contemplative delivery, Jordan Peterson's calmer moments, BBC documentary narrators
- **Design prompt:** "Mature male, deep contemplative voice, measured pacing, British-influenced accent, warm but intellectually rigorous, occasional gentle humor, late-night conversation energy"

### 4. Blues — Music / Harmonica
- **Target:** Older male, warm gravelly voice, relaxed southern American, blues musician energy
- **Search for:** Blues harmonica players giving lessons (Adam Gussow, Jason Ricci interviews), old blues documentaries, BB King interviews, porch storytelling energy
- **Design prompt:** "Older male, warm gravelly voice, relaxed southern American inflection, storytelling cadence, blues musician energy, porch wisdom"

### 5. Dr. Nova — Science / Physics
- **Target:** Middle-aged, gender-neutral, enthusiastic but precise, wonder in the voice
- **Search for:** Neil deGrasse Tyson's wonder moments, Brian Cox lectures, physics YouTubers (Veritasium, PBS Space Time), Carl Sagan delivery style
- **Design prompt:** "Middle-aged, gender-neutral, enthusiastic but precise, wonder in the voice, someone who finds the universe genuinely miraculous, clear for technical concepts"

### 6. Professor Clarity — Mathematics
- **Target:** Young professional female, extremely clear articulation, patient, calm confidence
- **Search for:** 3Blue1Brown female collaborators, Khan Academy-style female math tutors, patient math explainers on YouTube
- **Design prompt:** "Young professional female, extremely clear articulation, patient, encouraging when students struggle, calm confidence"

### 7. The Chronicler — History
- **Target:** Mature male, rich storytelling voice, dramatic but not theatrical, documentary narrator energy
- **Search for:** Dan Carlin (Hardcore History), history documentary narrators, Ken Burns narration style, dramatic history podcasters
- **Design prompt:** "Mature male, rich storytelling voice, dramatic but not theatrical, documentary narrator crossed with fireside storyteller"

### 8. The Muse — Writing / Creative
- **Target:** Young female, lyrical, expressive, varies pace, whispers for emphasis
- **Search for:** Spoken word poets (Sarah Kay, Amanda Gorman readings), creative writing teachers on MasterClass, lyrical female narrators
- **Design prompt:** "Young female, lyrical, expressive, varies pace, whispers for emphasis, energetic for exciting passages"

### 9. The Founder — Business / Entrepreneurship
- **Target:** Male, confident, direct, startup energy, speaks from experience
- **Search for:** Y Combinator talks, Gary Vaynerchuk calmer moments, startup founder interviews (Paul Graham, Naval Ravikant audio), confident but not bro-y
- **Design prompt:** "Male, confident, direct, startup energy, speaks from experience, occasional intensity"

### 10. Profesora Sofia — Spanish Language
- **Target:** Young Spanish female, warm, musical voice, natural rhythm between Spanish and English
- **Search for:** Spanish teachers on YouTube (Butterfly Spanish, SpanishPod101 female hosts), Latin/Spain-accented English speakers with warmth
- **Design prompt:** "Young Spanish female, warm, musical voice, natural rhythm between Spanish and English, encouraging, expressive"

## Output Format
Save a JSON file called `voice_references.json` in the project root with this structure:

```json
{
  "voices": [
    {
      "character_name": "Nonna Maria",
      "subject": "Italian Language",
      "design_prompt": "...",
      "refined_design_prompt": "... (updated after research)",
      "reference_clips": [
        {
          "url": "https://...",
          "timestamp": "2:15-3:45",
          "source_description": "Italian grandmother cooking tutorial",
          "match_quality": "excellent",
          "notes": "Perfect warm grandmother energy, slight accent"
        }
      ],
      "voice_design_notes": "Key traits to emphasize: ...",
      "elevenlabs_settings": {
        "stability": 0.55,
        "similarity_boost": 0.75,
        "style": 0.3,
        "model": "eleven_multilingual_v2"
      }
    }
  ],
  "scrape_date": "2026-03-09",
  "total_clips_found": 0,
  "status": "complete"
}
```

## Instructions for Cipher
1. Use `search_web` to find reference clips for each voice
2. Use `browser` to verify clips exist and note timestamps of best matching segments
3. For each voice, refine the ElevenLabs design prompt based on what real voices you find that match
4. Suggest optimal ElevenLabs voice settings (stability, similarity, style) per character
5. Save the complete `voice_references.json` to the project root using `write_file`
6. If you find a particularly perfect match for any voice, note it prominently

## Priority Order
Start with the most distinctive voices first:
1. Blues (most unique character)
2. Nonna Maria (strong cultural identity)
3. The Sage (Alan Watts is a clear reference)
4. The Chronicler (Dan Carlin is a clear reference)
5. Then the rest in order
