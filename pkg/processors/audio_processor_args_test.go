package processors

import (
    "strings"
    "testing"

    "github.com/paruff/Media-Refinery/pkg/logger"
    "github.com/paruff/Media-Refinery/pkg/metadata"
    "github.com/paruff/Media-Refinery/pkg/storage"
    "github.com/paruff/Media-Refinery/pkg/validator"
    "github.com/stretchr/testify/require"
)

func TestBuildFFmpegArgs_AudioFormats(t *testing.T) {
    tmp := t.TempDir()

    ctx := &ProcessorContext{
        Logger:    logger.NewLogger("debug", "text", nil),
        Storage:   storage.NewStorage(tmp, true),
        Validator: validator.NewValidator([]string{"mp3"}, []string{"mp4"}),
        Metadata:  metadata.NewMetadataExtractor(false),
        DryRun:    false,
    }

    meta := &metadata.Metadata{
        Title:  "Song Title",
        Artist: "Some Artist",
        Album:  "Some Album",
        Year:   "2020",
    }

    tests := []struct {
        name          string
        outputFormat  string
        outputQuality string
        bitDepth      int
        sampleRate    int
        meta          *metadata.Metadata
        wantSubstrs   []string
        dontWant      []string
    }{
        {
            name:         "flac with bitdepth and metadata",
            outputFormat: "flac",
            bitDepth:     16,
            sampleRate:   44100,
            meta:         meta,
            wantSubstrs: []string{"-c:a flac", "-sample_fmt s16", "-ar 44100", "-metadata title=Song Title", "-y"},
        },
        {
            name:          "mp3 lossless",
            outputFormat:  "mp3",
            outputQuality: "lossless",
            wantSubstrs:   []string{"-c:a libmp3lame", "-q:a 0", "-y"},
        },
        {
            name:          "mp3 default bitrate",
            outputFormat:  "mp3",
            outputQuality: "standard",
            wantSubstrs:   []string{"-c:a libmp3lame", "-b:a 320k", "-y"},
        },
        {
            name:         "aac default",
            outputFormat: "aac",
            wantSubstrs:  []string{"-c:a aac", "-b:a 256k", "-y"},
        },
        {
            name:         "no metadata when meta nil",
            outputFormat: "flac",
            bitDepth:     0,
            sampleRate:   0,
            meta:         nil,
            wantSubstrs:  []string{"-c:a flac", "-y"},
            dontWant:     []string{"-metadata"},
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            ap := NewAudioProcessor(ctx, tt.outputFormat, tt.outputQuality, false, tt.bitDepth, tt.sampleRate)
            args := ap.buildFFmpegArgs("infile.input", "outfile."+tt.outputFormat, tt.meta)
            joined := strings.Join(args, " ")

            for _, want := range tt.wantSubstrs {
                require.Contains(t, joined, want, "expected arg to contain %s; got: %v", want, args)
            }
            for _, no := range tt.dontWant {
                require.NotContains(t, joined, no, "did not expect arg %s; got: %v", no, args)
            }
        })
    }
}
