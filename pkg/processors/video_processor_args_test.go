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

func TestBuildFFmpegArgs_VideoFormats(t *testing.T) {
	tmp := t.TempDir()

	ctx := &ProcessorContext{
		Logger:    logger.NewLogger("debug", "text", nil),
		Storage:   storage.NewStorage(tmp, true),
		Validator: validator.NewValidator([]string{"mp3"}, []string{"mp4"}),
		Metadata:  metadata.NewMetadataExtractor(false),
		DryRun:    false,
	}

	meta := &metadata.Metadata{
		Title:   "Episode Title",
		Show:    "Show Name",
		Season:  "1",
		Episode: "2",
	}

	tests := []struct {
		name        string
		videoCodec  string
		audioCodec  string
		quality     string
		resolution  string
		meta        *metadata.Metadata
		wantSubstrs []string
	}{
		{
			name:        "h264 high quality",
			videoCodec:  "h264",
			audioCodec:  "aac",
			quality:     "high",
			resolution:  "1280x720",
			meta:        meta,
			wantSubstrs: []string{"-c:v libx264", "-preset slow", "-crf 16", "-c:a aac", "-b:a 192k", "-s 1280x720", "-metadata title=Episode Title", "-y"},
		},
		{
			name:        "h265 medium quality",
			videoCodec:  "h265",
			audioCodec:  "ac3",
			quality:     "medium",
			wantSubstrs: []string{"-c:v libx265", "-preset medium", "-crf 22", "-c:a ac3", "-b:a 384k", "-y"},
		},
		{
			name:        "copy audio/video",
			videoCodec:  "copy",
			audioCodec:  "copy",
			wantSubstrs: []string{"-c:v copy", "-c:a copy", "-y"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			vp := NewVideoProcessor(ctx, "mkv", tt.videoCodec, tt.audioCodec, tt.quality, tt.resolution)
			args := vp.buildFFmpegArgs("infile.input", "outfile.mkv", tt.meta)
			joined := strings.Join(args, " ")

			for _, want := range tt.wantSubstrs {
				require.Contains(t, joined, want, "expected arg to contain %s; got: %v", want, args)
			}
		})
	}
}
