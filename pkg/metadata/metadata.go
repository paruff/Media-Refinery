package metadata

import (
	"path/filepath"
	"strings"
)

// Metadata represents media file metadata
type Metadata struct {
	// Common fields
	Title       string
	Artist      string
	Album       string
	Year        string
	Genre       string
	Comment     string
	
	// Audio-specific
	Track       string
	TrackTotal  string
	Disc        string
	DiscTotal   string
	AlbumArtist string
	Composer    string
	
	// Video-specific
	Show        string
	Season      string
	Episode     string
	Director    string
	Actors      []string
	
	// Technical
	Duration    float64
	Bitrate     int
	SampleRate  int
	Channels    int
	
	// File info
	Format      string
	FilePath    string
}

// MetadataExtractor extracts metadata from media files
type MetadataExtractor struct {
	cleanupTags bool
}

// NewMetadataExtractor creates a new metadata extractor
func NewMetadataExtractor(cleanupTags bool) *MetadataExtractor {
	return &MetadataExtractor{
		cleanupTags: cleanupTags,
	}
}

// ExtractMetadata extracts metadata from a file
// In a real implementation, this would use libraries like taglib or ffprobe
func (e *MetadataExtractor) ExtractMetadata(path string) (*Metadata, error) {
	meta := &Metadata{
		FilePath: path,
		Format:   filepath.Ext(path),
	}
	
	// Parse filename for basic metadata (fallback)
	e.parseFilename(meta, path)
	
	return meta, nil
}

// parseFilename attempts to extract metadata from filename
func (e *MetadataExtractor) parseFilename(meta *Metadata, path string) {
	basename := filepath.Base(path)
	basename = strings.TrimSuffix(basename, filepath.Ext(basename))
	
	// Try to parse "Artist - Title" format
	if parts := strings.Split(basename, " - "); len(parts) >= 2 {
		meta.Artist = strings.TrimSpace(parts[0])
		meta.Title = strings.TrimSpace(parts[1])
	} else {
		meta.Title = basename
	}
	
	// Clean up if requested
	if e.cleanupTags {
		meta.Title = e.cleanTag(meta.Title)
		meta.Artist = e.cleanTag(meta.Artist)
	}
}

// cleanTag removes common artifacts from tags
func (e *MetadataExtractor) cleanTag(tag string) string {
	// Remove common patterns like [FLAC], (320kbps), etc.
	tag = strings.TrimSpace(tag)
	
	// Remove bracketed content
	for strings.Contains(tag, "[") && strings.Contains(tag, "]") {
		start := strings.Index(tag, "[")
		end := strings.Index(tag, "]")
		if start < end {
			tag = tag[:start] + tag[end+1:]
		}
	}
	
	// Remove parenthesized content (except years)
	for strings.Contains(tag, "(") && strings.Contains(tag, ")") {
		start := strings.Index(tag, "(")
		end := strings.Index(tag, ")")
		if start < end {
			content := tag[start+1 : end]
			// Keep if it looks like a year
			if len(content) == 4 && isNumeric(content) {
				break
			}
			tag = tag[:start] + tag[end+1:]
		}
	}
	
	return strings.TrimSpace(tag)
}

func isNumeric(s string) bool {
	for _, c := range s {
		if c < '0' || c > '9' {
			return false
		}
	}
	return len(s) > 0
}

// FormatPath formats a path using metadata and a pattern
func (e *MetadataExtractor) FormatPath(meta *Metadata, pattern string) string {
	result := pattern
	
	replacements := map[string]string{
		"{artist}":  sanitizeFilename(meta.Artist),
		"{album}":   sanitizeFilename(meta.Album),
		"{track}":   sanitizeFilename(meta.Track),
		"{title}":   sanitizeFilename(meta.Title),
		"{year}":    sanitizeFilename(meta.Year),
		"{show}":    sanitizeFilename(meta.Show),
		"{season}":  sanitizeFilename(meta.Season),
		"{episode}": sanitizeFilename(meta.Episode),
		"{type}":    "Unknown",
	}
	
	for placeholder, value := range replacements {
		if value != "" {
			result = strings.ReplaceAll(result, placeholder, value)
		}
	}
	
	return result
}

// sanitizeFilename removes invalid characters from filename
func sanitizeFilename(s string) string {
	if s == "" {
		return "Unknown"
	}
	
	// Remove or replace invalid characters
	invalid := []string{"/", "\\", ":", "*", "?", "\"", "<", ">", "|"}
	result := s
	for _, char := range invalid {
		result = strings.ReplaceAll(result, char, "_")
	}
	
	// Trim spaces and dots
	result = strings.TrimSpace(result)
	result = strings.Trim(result, ".")
	
	if result == "" {
		return "Unknown"
	}
	
	return result
}

// UpdateMetadata updates file metadata
// In a real implementation, this would use libraries to write tags
func (e *MetadataExtractor) UpdateMetadata(path string, meta *Metadata) error {
	// This is a placeholder - real implementation would write tags
	return nil
}

// ValidateMetadata validates metadata completeness
func (e *MetadataExtractor) ValidateMetadata(meta *Metadata) []string {
	var warnings []string
	
	if meta.Title == "" || meta.Title == "Unknown" {
		warnings = append(warnings, "missing title")
	}
	
	if meta.Artist == "" || meta.Artist == "Unknown" {
		warnings = append(warnings, "missing artist")
	}
	
	return warnings
}

// MergeMetadata merges two metadata objects, preferring non-empty values from the new metadata
func (e *MetadataExtractor) MergeMetadata(existing, new *Metadata) *Metadata {
	result := *existing
	
	if new.Title != "" {
		result.Title = new.Title
	}
	if new.Artist != "" {
		result.Artist = new.Artist
	}
	if new.Album != "" {
		result.Album = new.Album
	}
	if new.Year != "" {
		result.Year = new.Year
	}
	if new.Genre != "" {
		result.Genre = new.Genre
	}
	
	return &result
}
