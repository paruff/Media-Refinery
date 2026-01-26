package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/paruff/media-refinery/pkg/config"
	"github.com/paruff/media-refinery/pkg/logger"
	"github.com/paruff/media-refinery/pkg/pipeline"
)

const version = "1.0.0"

func main() {
	// Define flags
	configPath := flag.String("config", "", "Path to configuration file")
	inputDir := flag.String("input", "", "Input directory containing media files")
	outputDir := flag.String("output", "", "Output directory for processed files")
	dryRun := flag.Bool("dry-run", false, "Perform a dry run without modifying files")
	initConfig := flag.Bool("init", false, "Generate a default configuration file")
	showVersion := flag.Bool("version", false, "Show version information")
	logLevel := flag.String("log-level", "", "Log level (debug, info, warn, error)")
	concurrency := flag.Int("concurrency", 0, "Number of concurrent workers")
	
	flag.Parse()
	
	// Show version
	if *showVersion {
		fmt.Printf("Media Refinery v%s\n", version)
		fmt.Println("Production-grade media normalization pipeline")
		return
	}
	
	// Generate default config
	if *initConfig {
		if err := generateDefaultConfig(*configPath); err != nil {
			fmt.Fprintf(os.Stderr, "Error generating config: %v\n", err)
			os.Exit(1)
		}
		return
	}
	
	// Load configuration
	cfg, err := config.LoadConfig(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading config: %v\n", err)
		os.Exit(1)
	}
	
	// Override config with command-line flags
	if *inputDir != "" {
		cfg.InputDir = *inputDir
	}
	if *outputDir != "" {
		cfg.OutputDir = *outputDir
	}
	if *dryRun {
		cfg.DryRun = true
	}
	if *logLevel != "" {
		cfg.Logging.Level = *logLevel
	}
	if *concurrency > 0 {
		cfg.Concurrency = *concurrency
	}
	
	// Validate configuration
	if err := cfg.Validate(); err != nil {
		fmt.Fprintf(os.Stderr, "Invalid configuration: %v\n", err)
		os.Exit(1)
	}
	
	// Setup logger
	logOutput := os.Stdout
	if cfg.Logging.OutputFile != "" {
		file, err := os.OpenFile(cfg.Logging.OutputFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error opening log file: %v\n", err)
			os.Exit(1)
		}
		defer file.Close()
		logOutput = file
	}
	
	log := logger.NewLogger(cfg.Logging.Level, cfg.Logging.Format, logOutput)
	logger.SetDefaultLogger(log)
	
	// Create and run pipeline
	log.Info("Media Refinery v%s", version)
	
	pipe, err := pipeline.NewPipeline(cfg, log)
	if err != nil {
		log.Error("Failed to create pipeline: %v", err)
		os.Exit(1)
	}
	
	if err := pipe.Run(); err != nil {
		log.Error("Pipeline execution failed: %v", err)
		os.Exit(1)
	}
	
	log.Info("All operations completed successfully")
}

func generateDefaultConfig(path string) error {
	if path == "" {
		path = "config.yaml"
	}
	
	cfg := config.DefaultConfig()
	
	// Set some reasonable defaults for a new user
	cwd, err := os.Getwd()
	if err != nil {
		cwd = "."
	}
	
	cfg.InputDir = filepath.Join(cwd, "input")
	cfg.OutputDir = filepath.Join(cwd, "output")
	cfg.WorkDir = filepath.Join(cwd, "work")
	
	if err := cfg.SaveConfig(path); err != nil {
		return err
	}
	
	fmt.Printf("Generated default configuration file: %s\n", path)
	fmt.Println("\nEdit this file to customize your settings, then run:")
	fmt.Printf("  media-refinery -config %s\n", path)
	
	return nil
}
