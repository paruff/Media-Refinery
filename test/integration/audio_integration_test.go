package integration

import (
    "context"
    "os"
    "os/exec"
    "path/filepath"
    "testing"

    "github.com/paruff/Media-Refinery/pkg/config"
    "github.com/paruff/Media-Refinery/pkg/logger"
    "github.com/paruff/Media-Refinery/pkg/pipeline"
    "github.com/paruff/Media-Refinery/pkg/telemetry"
    "github.com/stretchr/testify/require"
)

// AudioIntegration covers high-level audio scenarios described in BDD feature
func TestAudioIntegration_Scenarios(t *testing.T) {
    cases := []struct {
        name         string
        dryRun       bool
        requireFFMpeg bool
    }{
        {name: "dry-run", dryRun: true, requireFFMpeg: false},
        {name: "real-conversion", dryRun: false, requireFFMpeg: true},
    }

    for _, tc := range cases {
        tc := tc
        t.Run(tc.name, func(t *testing.T) {
            if tc.requireFFMpeg {
                if _, err := exec.LookPath("ffprobe"); err != nil {
                    t.Skip("ffprobe not available; skipping real-conversion scenario")
                }
            }

            inputDir := t.TempDir()
            outputDir := t.TempDir()

            samplePath, _ := filepath.Abs("testdata/sample.mp3")
            // Ensure sample exists; if not, create a small silent WAV saved as .mp3 to satisfy tests
            if _, err := os.Stat(samplePath); os.IsNotExist(err) {
                if err := os.MkdirAll(filepath.Dir(samplePath), 0755); err != nil {
                    t.Fatalf("failed to create testdata dir: %v", err)
                }
                // Create a tiny WAV-like PCM file (silence) so file exists for tests
                data := make([]byte, 44+800) // small header + silence
                // Minimal RIFF/WAVE header (not fully populated but ffmpeg can often detect)
                copy(data[0:], []byte("RIFF"))
                copy(data[8:], []byte("WAVEfmt "))
                if err := os.WriteFile(samplePath, data, 0644); err != nil {
                    t.Fatalf("failed to write sample placeholder: %v", err)
                }
            }
            srcData, err := os.ReadFile(samplePath)
            require.NoError(t, err)
            require.NoError(t, os.WriteFile(filepath.Join(inputDir, "sample.mp3"), srcData, 0644))

            log := logger.NewLogger("info", "text", os.Stdout)
            tel, err := telemetry.Initialize(context.Background(), "Media-Refinery", "1.0.0")
            require.NoError(t, err)

            cfg := &config.Config{
                InputDir:  inputDir,
                OutputDir: outputDir,
                WorkDir:   t.TempDir(),
                DryRun:    tc.dryRun,
                Audio: config.AudioConfig{
                    Enabled:      true,
                    OutputFormat: "flac",
                    SupportedTypes: []string{"mp3", "flac", "aac", "m4a", "ogg", "wav"},
                },
                Video: config.VideoConfig{Enabled: false},
            }

            pipe, err := pipeline.NewPipeline(cfg, log, tel)
            require.NoError(t, err)

            require.NoError(t, pipe.Run(context.Background()))

            // Basic assertions are left to more specific integration tests; this scaffold ensures BDD scenarios run
        })
    }
}
package integration

import (
    "context"
    "os"
    "os/exec"
    "path/filepath"
    "testing"

    "github.com/paruff/Media-Refinery/pkg/config"
    "github.com/paruff/Media-Refinery/pkg/logger"
    "github.com/paruff/Media-Refinery/pkg/pipeline"
    "github.com/paruff/Media-Refinery/pkg/telemetry"
    "github.com/stretchr/testify/require"
)

// AudioIntegration covers high-level audio scenarios described in BDD feature
func TestAudioIntegration_Scenarios(t *testing.T) {
    cases := []struct {
        name         string
        dryRun       bool
        requireFFMpeg bool
    }{
        {name: "dry-run", dryRun: true, requireFFMpeg: false},
        {name: "real-conversion", dryRun: false, requireFFMpeg: true},
    }

    for _, tc := range cases {
        tc := tc
        t.Run(tc.name, func(t *testing.T) {
            if tc.requireFFMpeg {
                if _, err := exec.LookPath("ffprobe"); err != nil {
                    t.Skip("ffprobe not available; skipping real-conversion scenario")
                }
            }

            inputDir := t.TempDir()
            outputDir := t.TempDir()

            samplePath, _ := filepath.Abs("testdata/sample.mp3")
            // Ensure sample exists; if not, create a small silent WAV saved as .mp3 to satisfy tests
            if _, err := os.Stat(samplePath); os.IsNotExist(err) {
                if err := os.MkdirAll(filepath.Dir(samplePath), 0755); err != nil {
                    t.Fatalf("failed to create testdata dir: %v", err)
                }
                // Create a tiny WAV-like PCM file (silence) so file exists for tests
                data := make([]byte, 44+800) // small header + silence
                // Minimal RIFF/WAVE header (not fully populated but ffmpeg can often detect)
                copy(data[0:], []byte("RIFF"))
                copy(data[8:], []byte("WAVEfmt "))
                if err := os.WriteFile(samplePath, data, 0644); err != nil {
                    t.Fatalf("failed to write sample placeholder: %v", err)
                }
            }
            srcData, err := os.ReadFile(samplePath)
            require.NoError(t, err)
            require.NoError(t, os.WriteFile(filepath.Join(inputDir, "sample.mp3"), srcData, 0644))

            log := logger.NewLogger("info", "text", os.Stdout)
            tel, err := telemetry.Initialize(context.Background(), "Media-Refinery", "1.0.0")
            require.NoError(t, err)

            cfg := &config.Config{
                InputDir:  inputDir,
                OutputDir: outputDir,
                WorkDir:   t.TempDir(),
                DryRun:    tc.dryRun,
                Audio: config.AudioConfig{
                    Enabled:      true,
                    OutputFormat: "flac",
                    SupportedTypes: []string{"mp3", "flac", "aac", "m4a", "ogg", "wav"},
                },
                Video: config.VideoConfig{Enabled: false},
            }

            pipe, err := pipeline.NewPipeline(cfg, log, tel)
            require.NoError(t, err)

            require.NoError(t, pipe.Run(context.Background()))

            // Basic assertions are left to more specific integration tests; this scaffold ensures BDD scenarios run
        })
    }
}
