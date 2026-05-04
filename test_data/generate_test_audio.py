"""
Generate test audio files for Korean speech testing.
Uses gTTS (Google Text-to-Speech) to create synthetic Korean audio.
"""

import json
import os
from pathlib import Path

try:
    from gtts import gTTS
except ImportError:
    print("Installing gTTS...")
    import subprocess
    subprocess.run(["pip", "install", "gtts"], check=True)
    from gtts import gTTS


def generate_korean_audio(text: str, output_path: str, lang: str = "ko") -> bool:
    """Generate Korean audio using Google TTS."""
    try:
        tts = gTTS(text=text, lang=lang, slow=False)
        tts.save(output_path)
        print(f"Generated: {output_path}")
        return True
    except Exception as e:
        print(f"Error generating {output_path}: {e}")
        return False


def convert_to_wav(input_path: str, output_path: str) -> bool:
    """Convert audio to WAV 16kHz mono using ffmpeg."""
    import subprocess
    try:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-ar", "16000", "-ac", "1",
            "-c:a", "pcm_s16le", output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"Converted to WAV: {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting {input_path}: {e}")
        return False
    except FileNotFoundError:
        print("ffmpeg not found. Please install ffmpeg.")
        return False


def main():
    # Load sample phrases
    with open("sample_korean_phrases.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    output_dir = Path("audio_samples")
    output_dir.mkdir(exist_ok=True)

    print("Generating Korean test audio samples...")
    print("=" * 60)

    generated = []
    for phrase in data["sample_phrases"]:
        phrase_id = phrase["id"]
        korean_text = phrase["korean"]

        mp3_path = output_dir / f"{phrase_id}.mp3"
        wav_path = output_dir / f"{phrase_id}.wav"

        if generate_korean_audio(korean_text, str(mp3_path)):
            if convert_to_wav(str(mp3_path), str(wav_path)):
                generated.append({
                    "id": phrase_id,
                    "wav_path": str(wav_path),
                    "text": korean_text,
                    "duration_estimate": phrase.get("duration_seconds", 5.0)
                })
                # Remove MP3, keep only WAV
                mp3_path.unlink()

    # Save manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(generated, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"Generated {len(generated)} audio samples in {output_dir}/")
    print(f"Manifest saved to: {manifest_path}")

    # Create combined test chunks (15 seconds each)
    create_test_chunks(output_dir, generated)


def create_test_chunks(output_dir: Path, samples: list):
    """Create 15-second test chunks by concatenating samples."""
    import subprocess

    print("\nCreating 15-second test chunks...")
    chunk_dir = output_dir / "chunks"
    chunk_dir.mkdir(exist_ok=True)

    # Create a 15-second chunk
    target_duration = 15.0
    current_duration = 0.0
    chunk_files = []
    chunk_idx = 0

    for sample in samples:
        sample_duration = sample.get("duration_estimate", 5.0)

        if current_duration + sample_duration > target_duration and chunk_files:
            # Create chunk
            output_wav = chunk_dir / f"chunk_{chunk_idx:03d}.wav"
            create_concatenated_wav(chunk_files, str(output_wav))
            print(f"Created: {output_wav}")
            chunk_idx += 1
            chunk_files = []
            current_duration = 0.0

        chunk_files.append(sample["wav_path"])
        current_duration += sample_duration

    # Create final chunk if there are remaining files
    if chunk_files:
        output_wav = chunk_dir / f"chunk_{chunk_idx:03d}.wav"
        create_concatenated_wav(chunk_files, str(output_wav))
        print(f"Created: {output_wav}")

    print(f"Test chunks saved to: {chunk_dir}/")


def create_concatenated_wav(input_files: list, output_path: str):
    """Concatenate multiple WAV files using ffmpeg."""
    import subprocess
    import tempfile

    # Create concat list file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        for wav_file in input_files:
            f.write(f"file '{wav_file}'\n")
        list_file = f.name

    try:
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-ar", "16000", "-ac", "1",
            "-c:a", "pcm_s16le", output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    finally:
        Path(list_file).unlink()


if __name__ == "__main__":
    main()
