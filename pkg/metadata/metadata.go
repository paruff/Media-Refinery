package metadata

import (
	"encoding/json"
	"fmt"
	"os/exec"
	"path/filepath"
	"strconv"
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

// ExtractMetadata extracts metadata from a file using ffprobe
func (e *MetadataExtractor) ExtractMetadata(path string) (*Metadata, error) {
	meta := &Metadata{
		FilePath: path,
		Format:   strings.TrimPrefix(filepath.Ext(path), "."),
	}
	
	// Use ffprobe to extract metadata
	cmd := exec.Command("ffprobe",
		"-v", "quiet",
		"-print_format", "json",
		"-show_format",
		"-show_streams",
		path,
	)
	
	output, err := cmd.Output()
	if err != nil {
		// Fallback to filename parsing
		e.parseFilename(meta, path)
		return meta, nil
	}
	
	var result struct {
		Format struct {
			Tags map[string]string `json:"tags"`
			Duration string `json:"duration"`
			BitRate string `json:"bit_rate"`
		} `json:"format"`
		Streams []struct {
			CodecType string `json:"codec_type"`
			SampleRate string `json:"sample_rate"`
			Channels int `json:"channels"`
		} `json:"streams"`
	}
	
	if err := json.Unmarshal(output, &result); err != nil {
		e.parseFilename(meta, path)
		return meta, nil
	}
	
	// Extract tags (case-insensitive)
	tags := make(map[string]string)
	for k, v := range result.Format.Tags {
		tags[strings.ToLower(k)] = v
	}
	
	// Map common tag names
	meta.Title = getTag(tags, "title", "TITLE")
	meta.Artist = getTag(tags, "artist", "ARTIST")
	meta.Album = getTag(tags, "album", "ALBUM")
	meta.AlbumArtist = getTag(tags, "album_artist", "albumartist", "ALBUM_ARTIST", "ALBUMARTIST")
	meta.Year = getTag(tags, "year", "date", "YEAR", "DATE")
	meta.Genre = getTag(tags, "genre", "GENRE")
	meta.Track = getTag(tags, "track", "TRACK", "tracknumber", "TRACKNUMBER")
	meta.Composer = getTag(tags, "composer", "COMPOSER")
	meta.Comment = getTag(tags, "comment", "COMMENT")
	
	// Video-specific metadata
	meta.Show = getTag(tags, "show", "SHOW", "series", "SERIES")
	meta.Season = getTag(tags, "season", "SEASON", "season_number", "SEASON_NUMBER")
	meta.Episode = getTag(tags, "episode", "EPISODE", "episode_id", "EPISODE_ID")
	meta.Director = getTag(tags, "director", "DIRECTOR")
	
	// Parse duration
	if result.Format.Duration != "" {
		if d, err := strconv.ParseFloat(result.Format.Duration, 64); err == nil {
			meta.Duration = d
		}
	}
	
	// Parse bitrate
	if result.Format.BitRate != "" {
		if br, err := strconv.Atoi(result.Format.BitRate); err == nil {
			meta.Bitrate = br
		}
	}
	
	// Extract audio stream info
	for _, stream := range result.Streams {
		if stream.CodecType == "audio" {
			if stream.SampleRate != "" {
				if sr, err := strconv.Atoi(stream.SampleRate); err == nil {
					meta.SampleRate = sr
				}
			}
			meta.Channels = stream.Channels
			break
		}
	}
	
	// Fallback to filename if no tags found
	if meta.Title == "" && meta.Artist == "" {
		e.parseFilename(meta, path)
	}
	
	// Clean up if requested
	if e.cleanupTags {
		meta.Title = e.cleanTag(meta.Title)
		meta.Artist = e.cleanTag(meta.Artist)
		meta.Album = e.cleanTag(meta.Album)
	}
	
	return meta, nil
}

// getTag retrieves a tag value by trying multiple possible keys
func getTag(tags map[string]string, keys ...string) string {
	for _, key := range keys {
		if val, ok := tags[strings.ToLower(key)]; ok && val != "" {
			return val
		}
	}
	return ""
}

// parseFilename attempts to extract metadata from filename
func (e *MetadataExtractor) parseFilename(meta *Metadata, path string) {
	basename := filepath.Base(path)
	basename = strings.TrimSuffix(basename, filepath.Ext(basename))
	
	// Check for TV series pattern (e.g., "Show.Name.S01E02" or "Show Name - S01E02")
	if strings.Contains(strings.ToUpper(basename), "S") && strings.Contains(strings.ToUpper(basename), "E") {
		// Try to extract season/episode (S01E02 format)
		for i := 0; i < len(basename)-4; i++ {
			if (basename[i] == 'S' || basename[i] == 's') && 
			   (basename[i+3] == 'E' || basename[i+3] == 'e') {
				if isNumeric(basename[i+1:i+3]) && isNumeric(basename[i+4:min(i+6, len(basename))]) {
					meta.Season = basename[i+1:i+3]
					meta.Episode = basename[i+4:min(i+6, len(basename))]
					meta.Show = strings.TrimSpace(strings.ReplaceAll(strings.ReplaceAll(basename[:i], ".", " "), "_", " "))
					meta.Title = meta.Show
					return
				}
			}
		}
	}
	
	// Check for movie pattern with year (e.g., "Movie Title (1999)")
	if strings.Contains(basename, "(") && strings.Contains(basename, ")") {
		start := strings.LastIndex(basename, "(")
		end := strings.LastIndex(basename, ")")
		if start < end && end-start == 5 {
			yearStr := basename[start+1:end]
			if isNumeric(yearStr) && len(yearStr) == 4 {
				meta.Year = yearStr
				meta.Title = strings.TrimSpace(strings.ReplaceAll(strings.ReplaceAll(basename[:start], ".", " "), "_", " "))
				return
			}
		}
	}
	
	// Try to parse "Artist - Title" format for music
	if parts := strings.Split(basename, " - "); len(parts) >= 2 {
		meta.Artist = strings.TrimSpace(parts[0])
		meta.Title = strings.TrimSpace(parts[1])
	} else {
		// Clean up dots and underscores for title
		meta.Title = strings.TrimSpace(strings.ReplaceAll(strings.ReplaceAll(basename, ".", " "), "_", " "))
	}
	
	// Clean up if requested
	if e.cleanupTags {
		meta.Title = e.cleanTag(meta.Title)
		meta.Artist = e.cleanTag(meta.Artist)
		meta.Show = e.cleanTag(meta.Show)
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
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
func (e *MetadataExtractor) FormatPath(meta *Metadata, pattern string, mediaType string) string {
	result := pattern
	
	// Determine media type prefix
	var typePrefix string
	if mediaType == "audio" {
		typePrefix = "music"
	} else if mediaType == "video" {
		// Check if it's a TV series or movie
		if meta.Season != "" || meta.Episode != "" || meta.Show != "" {
			typePrefix = "series"
		} else {
			typePrefix = "movies"
		}
	}
	
	replacements := map[string]string{
		"{artist}":  sanitizeFilename(meta.Artist),
		"{album}":   sanitizeFilename(meta.Album),
		"{track}":   sanitizeFilename(meta.Track),
		"{title}":   sanitizeFilename(meta.Title),
		"{year}":    sanitizeFilename(meta.Year),
		"{show}":    sanitizeFilename(meta.Show),
		"{season}":  sanitizeFilename(meta.Season),
		"{episode}": sanitizeFilename(meta.Episode),
		"{type}":    typePrefix,
	}
	
	for placeholder, value := range replacements {
		if value != "" && value != "Unknown" {
			result = strings.ReplaceAll(result, placeholder, value)
		}
	}
	
	// Add type prefix
	if typePrefix != "" {
		result = filepath.Join(typePrefix, result)
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

// UpdateMetadata updates file metadata using ffmpeg
func (e *MetadataExtractor) UpdateMetadata(path string, meta *Metadata) error {
	if meta == nil {
		return nil
	}
	
	// Build ffmpeg metadata arguments
	args := []string{"-i", path, "-c", "copy"}
	
	// Add metadata tags
	if meta.Title != "" && meta.Title != "Unknown" {
		args = append(args, "-metadata", "title="+meta.Title)
	}
	if meta.Artist != "" && meta.Artist != "Unknown" {
		args = append(args, "-metadata", "artist="+meta.Artist)
	}
	if meta.Album != "" && meta.Album != "Unknown" {
		args = append(args, "-metadata", "album="+meta.Album)
	}
	if meta.AlbumArtist != "" && meta.AlbumArtist != "Unknown" {
		args = append(args, "-metadata", "album_artist="+meta.AlbumArtist)
	}
	if meta.Year != "" && meta.Year != "Unknown" {
		args = append(args, "-metadata", "date="+meta.Year)
	}
	if meta.Genre != "" && meta.Genre != "Unknown" {
		args = append(args, "-metadata", "genre="+meta.Genre)
	}
	if meta.Track != "" && meta.Track != "Unknown" {
		args = append(args, "-metadata", "track="+meta.Track)
	}
	if meta.Composer != "" && meta.Composer != "Unknown" {
		args = append(args, "-metadata", "composer="+meta.Composer)
	}
	
	// Only proceed if we have metadata to write
	if len(args) <= 4 { // Just "-i path -c copy"
		return nil
	}
	
	// Create temp file
	tempPath := path + ".tmp"
	args = append(args, "-y", tempPath)
	
	cmd := exec.Command("ffmpeg", args...)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("failed to update metadata: %w", err)
	}
	
	// Replace original with temp file
	if err := exec.Command("mv", tempPath, path).Run(); err != nil {
		return fmt.Errorf("failed to replace file: %w", err)
	}
	
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
