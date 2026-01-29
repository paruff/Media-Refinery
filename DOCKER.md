# Docker Setup Guide

This guide explains how to set up and run Media Refinery with all integrations using Docker.

## Quick Start

1. **Clone the repository:**
```bash
git clone https://github.com/paruff/Media-Refinery.git
cd media-refinery
```

2. **Create configuration file:**
```bash
cp config.example.yaml config.yaml
```

3. **Create required directories:**
```bash
mkdir -p input output work config/{beets,tdarr,radarr,sonarr,plex}
```

4. **Start all services:**
```bash
docker-compose up -d
```

5. **Check service status:**
```bash
docker-compose ps
```

## Service Configuration

### Beets (Music Management)

1. **Access Beets:**
   - URL: http://localhost:8337
   
2. **Configure Beets:**
   - Edit `config/beets/config.yaml`
   - Set your music directory
   - Enable web interface:
     ```yaml
     plugins: web
     web:
       host: 0.0.0.0
       port: 8337
     ```

3. **Get API Token (if needed):**
   ```bash
   docker exec -it beets beet config
   ```

### Tdarr (Transcoding)

1. **Access Tdarr:**
   - URL: http://localhost:8265
   
2. **Initial Setup:**
   - Create an account on first visit
   - Go to Libraries → Add Library
   - Set source folder: `/input`
   - Set output folder: `/output`
   - Set transcode cache: `/temp`

3. **Get API Key:**
   - Settings → General → API Key
   - Copy key to `config.yaml` under `integrations.tdarr.api_key`

4. **Configure Transcoding:**
   - Go to Transcode Options
   - Select desired plugins (H264/AAC for compatibility)
   - Set quality settings

### Radarr (Movies)

1. **Access Radarr:**
   - URL: http://localhost:7878
   
2. **Initial Setup:**
   - Complete the setup wizard
   - Add root folder: `/movies`
   - Configure quality profiles
   - Set naming scheme for Plex

3. **Get API Key:**
   - Settings → General → Security → API Key
   - Copy key to `config.yaml` under `integrations.radarr.api_key`

4. **Naming Configuration:**
   - Settings → Media Management
   - Standard Movie Format: `{Movie Title} ({Release Year})`
   - Movie Folder Format: `{Movie Title} ({Release Year})`

### Sonarr (TV Shows)

1. **Access Sonarr:**
   - URL: http://localhost:8989
   
2. **Initial Setup:**
   - Complete the setup wizard
   - Add root folder: `/tv`
   - Configure quality profiles
   - Set naming scheme for Plex

3. **Get API Key:**
   - Settings → General → Security → API Key
   - Copy key to `config.yaml` under `integrations.sonarr.api_key`

4. **Naming Configuration:**
   - Settings → Media Management
   - Standard Episode Format: `{Series Title} - S{season:00}E{episode:00} - {Episode Title}`
   - Season Folder Format: `Season {season:00}`

### Plex (Optional)

1. **Access Plex:**
   - URL: http://localhost:32400/web
   
2. **Initial Setup:**
   - Sign in with Plex account
   - Add libraries pointing to `/data/music` and `/data/videos`

## Running Media Refinery

### Option 1: One-time Run

```bash
docker-compose run --rm media-refinery -config /app/config.yaml
```

### Option 2: Dry Run First

```bash
docker-compose run --rm media-refinery -config /app/config.yaml -dry-run
```

### Option 3: With Custom Settings

```bash
docker-compose run --rm media-refinery \
  -config /app/config.yaml \
  -input /input \
  -output /output \
  -concurrency 8
```

## Configuration Updates

After setting up the integrations, update your `config.yaml`:

```yaml
integrations:
  beets:
    enabled: true
    url: http://beets:8337
    token: ""  # Add if authentication is enabled

  tdarr:
    enabled: true
    url: http://tdarr:8265
    api_key: "YOUR_TDARR_API_KEY"
    library_id: "1"

  radarr:
    enabled: true
    url: http://radarr:7878
    api_key: "YOUR_RADARR_API_KEY"

  sonarr:
    enabled: true
    url: http://sonarr:8989
    api_key: "YOUR_SONARR_API_KEY"
```

## Directory Structure

After setup, your directory structure should look like:

```
media-refinery/
├── input/              # Place your media files here
│   ├── music/
│   ├── movies/
│   └── tv/
├── output/             # Processed files go here
│   ├── Music/
│   ├── Movies/
│   └── TV Shows/
├── work/               # Temporary processing directory
├── config/             # Service configurations
│   ├── beets/
│   ├── tdarr/
│   ├── radarr/
│   ├── sonarr/
│   └── plex/
├── config.yaml         # Media Refinery config
└── docker-compose.yml
```

## Workflow

1. **Place media files in input directory:**
   ```bash
   cp /path/to/your/media/* ./input/
   ```

2. **Run dry-run to preview operations:**
   ```bash
   docker-compose run --rm media-refinery -dry-run
   ```

3. **Review the output and adjust config if needed**

4. **Run actual processing:**
   ```bash
   docker-compose run --rm media-refinery
   ```

5. **Check output directory for processed files**

6. **Scan libraries in Plex/Music Assistant**

## Integration Flow

### Audio Processing Flow
1. Media Refinery scans input files
2. Queries Beets for metadata
3. Converts to FLAC (if needed)
4. Organizes using Beets naming conventions
5. Optionally imports to Beets library

### Video Processing Flow (Movies)
1. Media Refinery scans input files
2. Queries Radarr for movie metadata
3. Submits to Tdarr for transcoding (if enabled)
4. Uses Radarr naming conventions
5. Outputs to Plex-compatible structure

### Video Processing Flow (TV)
1. Media Refinery scans input files
2. Queries Sonarr for series/episode metadata
3. Submits to Tdarr for transcoding (if enabled)
4. Uses Sonarr naming conventions
5. Outputs to Plex-compatible structure

## Troubleshooting

### Services not starting
```bash
# Check logs
docker-compose logs -f

# Restart specific service
docker-compose restart radarr
```

### Permission issues
```bash
# Fix permissions
sudo chown -R 1000:1000 input output work config
```

### API connection errors
```bash
# Test connectivity
docker exec -it media-refinery ping radarr

# Check API keys
docker-compose run --rm media-refinery -config /app/config.yaml
# Look for health check messages in logs
```

### Cannot access web interfaces
```bash
# Check if ports are bound
docker-compose ps

# Check firewall rules
sudo ufw status
```

## Advanced Configuration

### Custom Docker Network

If you have existing services on a different network:

```yaml
networks:
  media-refinery-network:
    external: true
    name: your-existing-network
```

### Resource Limits

Add resource limits for transcoding:

```yaml
services:
  tdarr:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
```

### GPU Transcoding (Tdarr)

For NVIDIA GPU support:

```yaml
services:
  tdarr:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

## Monitoring

### View logs in real-time
```bash
docker-compose logs -f media-refinery
```

### Check processing stats
```bash
docker-compose run --rm media-refinery -config /app/config.yaml
# Look for "Processing Statistics" at the end
```

## Backup and Maintenance

### Backup configurations
```bash
tar -czf media-refinery-backup.tar.gz config/ config.yaml
```

### Update containers
```bash
docker-compose pull
docker-compose up -d
```

### Clean up
```bash
# Remove stopped containers
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v
```

## Security Notes

1. **Change default passwords** for all services
2. **Keep API keys private** - don't commit config.yaml with keys
3. **Use environment variables** for sensitive data:
   ```yaml
   api_key: ${RADARR_API_KEY}
   ```
4. **Restrict network access** if exposed to internet
5. **Regular updates** - run `docker-compose pull` periodically

## Performance Tuning

1. **Adjust concurrency** based on CPU cores:
   ```yaml
   concurrency: 8  # Set to number of CPU cores
   ```

2. **Use SSD for work directory** for faster processing

3. **Separate input/output** to different disks for I/O parallelism

4. **Monitor resource usage:**
   ```bash
   docker stats
   ```

## Support

For issues and questions:
- Check logs: `docker-compose logs`
- Review configuration: `config.yaml`
- Verify integrations are healthy
- See main README for more details
