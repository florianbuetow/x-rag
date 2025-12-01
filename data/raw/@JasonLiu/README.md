# Video Transcripts - @JasonLiu

This folder contains video transcripts from content created by or featuring Jason Liu. The transcripts capture spoken content from various videos and have been processed to provide text-based access to the information presented.

**Note**: This directory may contain multiple subdirectories with different transcription sources and models. The metadata specifications below apply only to files in the `medium-en` subfolder.

## Content Description

The files in this directory are raw, unstructured transcripts of video content. Each transcript represents a linear, chronological record of spoken dialogue from the original video source.

### Characteristics

- **Language**: English only
- **Speakers**: Mix of single-speaker and multi-speaker scenarios
- **Format**: Plain text with basic formatting and punctuation
- **Structure**: Linear transcription following the video timeline
- **Organization**: Minimal structural organization beyond chronological flow

## Usage Notes

These transcripts are provided as raw data for further processing, analysis, or indexing. The text has not been edited for clarity, organized into sections, or enhanced with additional structure beyond what was captured during the transcription process.

Users of this data should be aware that:
- Speaker attribution may vary across files
- Punctuation and formatting are basic
- No semantic or topical organization has been applied
- The transcripts reflect natural speech patterns, including filler words and incomplete sentences

## Metadata

### `medium-en` Subfolder

The following metadata applies specifically to files located in the `medium-en` subfolder:

| Property | Value |
|----------|-------|
| Content Type | Video Transcripts |
| File Format | Plain text files (`.txt`) with accompanying JSON metadata files (`.json`) |
| Transcription Model | OpenAI Whisper (medium, English) |
| Language | English |
| Source | @JasonLiu video content |
| Processing Status | Raw/Unstructured |
| Filename Convention | Each filename corresponds to the title of the source video |

#### JSON Metadata Files

Each transcript file has a corresponding JSON metadata file with the same base name. For example, `Example Video.txt` has a companion file `Example Video.json`.

The JSON files follow this structure:
```json
{
  "metadata": {
    "title": "Example Video",
    "source_file": "Example Video.txt",
    "type": "video transcript",
    "transcription_method": "whisper (medium, English)"
  }
}
```

Where:
- `title`: The video title (filename without the .txt extension)
- `source_file`: The original transcript filename including the .txt extension
- `type`: Content type identifier
- `transcription_method`: The model and configuration used for transcription

**Note**: Other subfolders may be added in the future with different transcription models, file formats, or source types.
