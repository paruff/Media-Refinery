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
            require.NoError(t, os.RemoveAll(samplePath)) // noop if not present
            // Copy sample to input dir (test expects repository testdata/sample.mp3 to exist)
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
