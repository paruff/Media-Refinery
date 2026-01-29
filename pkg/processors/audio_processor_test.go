package processors

import (
    "context"
    "testing"

    "github.com/paruff/Media-Refinery/pkg/logger"
    "github.com/paruff/Media-Refinery/pkg/metadata"
    "github.com/paruff/Media-Refinery/pkg/storage"
    "github.com/paruff/Media-Refinery/pkg/validator"
)

// NOTE: This file contains scaffolding tests for audio processor behavior.
// Later refactor: factor ffmpeg arg construction into a helper so we can assert args without invoking ffmpeg.

func TestAudioProcessor_DryRunDoesNotInvokeFFmpeg(t *testing.T) {
    // Create a minimal ProcessorContext with DryRun=true so conversion path avoids calling ffmpeg
    ctx := &ProcessorContext{
        Logger:    logger.NewLogger("debug", "text", nil),
        Storage:   storage.NewStorage("/tmp", true),
        Validator: validator.NewValidator([]string{"mp3"}, []string{"mp4"}),
        Metadata:  metadata.NewMetadataExtractor(false),
        DryRun:    true,
    }

    ap := NewAudioProcessor(ctx, "flac", "lossless", false, 16, 44100)

    // Call Process on a non-existent file path; because DryRun=true Process should return nil after logging
    if err := ap.Process(context.Background(), "/no/such/file.mp3", "/out/file.flac"); err != nil {
        t.Fatalf("expected no error in dry-run path, got: %v", err)
    }
}
