# Test Data for Korean Meeting Interpreter

## Sample Korean Phrases

El archivo `sample_korean_phrases.json` contiene frases de prueba coreanas con traducciones a español, inglés y chino.

### Categorías

1. **Meeting Start** - Frases de apertura de reuniones
2. **Project Presentation** - Presentaciones técnicas
3. **Technical Presentation** - Discusiones de NLP/AI
4. **Deadline Reminder** - Recordatorios de plazos
5. **Data Presentation** - Análisis de datos médicos
6. **Presentation Flow** - Transiciones en presentaciones
7. **Results Presentation** - Métricas y resultados

## Generación de Audio de Prueba

### Opción 1: gTTS (Automático)

```bash
cd test_data
pip install gtts
python generate_test_audio.py
```

Esto generará archivos WAV de 15 segundos usando Google Text-to-Speech.

### Opción 2: ffmpeg (Sin dependencias)

```bash
# Generar audio dummy WAV 16kHz mono
ffmpeg -f lavfi -i "sine=frequency=1000:duration=15" -ar 16000 -ac 1 test_korean.wav
```

### Opción 3: Datasets Online

| Fuente | URL | Descripción |
|--------|-----|-------------|
| Mozilla Common Voice | https://commonvoice.mozilla.org/ | Dataset abierto con muestras coreanas (CC0) |
| AI Hub Korean Speech | https://aihub.or.kr/ | Datos del gobierno coreano |
| Zeroth-Korean | https://github.com/goodatlas/zeroth | Dataset Kaldi para ASR coreano |
| Korean Single Speaker | https://www.kaggle.com/datasets | Buscar "korean speech" en Kaggle |

## Formato de Audio Requerido

- **Formato**: WAV
- **Sample Rate**: 16000 Hz
- **Canales**: Mono (1)
- **Codec**: PCM 16-bit
- **Duración**: 15 segundos por chunk

## Estructura de Archivos

```
test_data/
├── sample_korean_phrases.json    # Frases de prueba
├── generate_test_audio.py        # Script generador
├── audio_samples/               # Audios generados
│   ├── ko-001.wav
│   ├── ko-002.wav
│   └── manifest.json
└── chunks/                      # Chunks de 15 segundos
    ├── chunk_000.wav
    └── chunk_001.wav
```

## Uso en Tests

```python
# Upload chunk de prueba
with open("test_data/chunks/chunk_000.wav", "rb") as f:
    audio_bytes = f.read()
    upload_chunk(audio_bytes, chunk_index=0)
```
