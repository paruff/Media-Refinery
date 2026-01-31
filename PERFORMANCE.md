# Performance Guide

## Benchmarks

### Audio Conversion (MP3 → FLAC)
- **Single file (5MB)**: ~3 seconds
- **Batch (100 files, 4 workers)**: ~75 seconds (4x speedup)
- **Memory usage**: ~200MB peak

### Video Conversion (MP4 → MKV)
- **Single file (1GB)**: ~120 seconds
- **Batch (10 files, 4 workers)**: ~300 seconds (4x speedup)
- **Memory usage**: ~500MB peak

## Optimization Tips

### 1. Tune Worker Count
```python
# CPU-bound: use CPU count
workers = os.cpu_count()

# I/O-bound: use 2-4x CPU count
workers = os.cpu_count() * 2
```

### 2. Use SSD for Work Directory
```yaml
# config.yaml
work_dir: /ssd/media-refinery/work
```

### 3. Enable Hardware Acceleration (Video)
```yaml
video:
  hardware_acceleration: true
  encoder: h264_nvenc  # NVIDIA GPU
```

### 4. Adjust Compression Levels
```yaml
audio:
  compression_level: 5  # 0-8, higher = slower but smaller
```

## Profiling
```bash
# Profile with py-spy
py-spy record -o profile.svg -- python run_refinery.py

# Memory profiling
python -m memory_profiler run_refinery.py
```
