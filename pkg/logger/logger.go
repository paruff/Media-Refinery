package logger

import (
	"fmt"
	"io"
	"log"
	"os"
	"sync"
	"time"
)

// Level represents the log level
type Level int

const (
	DebugLevel Level = iota
	InfoLevel
	WarnLevel
	ErrorLevel
)

// Logger provides structured logging with observability
type Logger struct {
	mu       sync.Mutex
	level    Level
	format   string
	output   io.Writer
	prefix   string
	counters map[string]int64
}

var (
	defaultLogger *Logger
	once          sync.Once
)

// NewLogger creates a new logger instance
func NewLogger(level, format string, output io.Writer) *Logger {
	l := &Logger{
		level:    parseLevel(level),
		format:   format,
		output:   output,
		counters: make(map[string]int64),
	}
	
	if output == nil {
		l.output = os.Stdout
	}
	
	return l
}

// GetLogger returns the default logger instance
func GetLogger() *Logger {
	once.Do(func() {
		defaultLogger = NewLogger("info", "text", os.Stdout)
	})
	return defaultLogger
}

// SetDefaultLogger sets the default logger
func SetDefaultLogger(logger *Logger) {
	defaultLogger = logger
}

func parseLevel(level string) Level {
	switch level {
	case "debug":
		return DebugLevel
	case "info":
		return InfoLevel
	case "warn", "warning":
		return WarnLevel
	case "error":
		return ErrorLevel
	default:
		return InfoLevel
	}
}

func (l *Logger) log(level Level, format string, args ...interface{}) {
	if level < l.level {
		return
	}
	
	l.mu.Lock()
	defer l.mu.Unlock()
	
	levelStr := ""
	switch level {
	case DebugLevel:
		levelStr = "DEBUG"
	case InfoLevel:
		levelStr = "INFO"
	case WarnLevel:
		levelStr = "WARN"
	case ErrorLevel:
		levelStr = "ERROR"
	}
	
	timestamp := time.Now().Format("2006-01-02 15:04:05")
	msg := fmt.Sprintf(format, args...)
	
	if l.format == "json" {
		fmt.Fprintf(l.output, `{"time":"%s","level":"%s","msg":"%s"}`+"\n",
			timestamp, levelStr, msg)
	} else {
		fmt.Fprintf(l.output, "[%s] %s: %s\n", timestamp, levelStr, msg)
	}
}

// Debug logs a debug message
func (l *Logger) Debug(format string, args ...interface{}) {
	l.log(DebugLevel, format, args...)
}

// Info logs an info message
func (l *Logger) Info(format string, args ...interface{}) {
	l.log(InfoLevel, format, args...)
}

// Warn logs a warning message
func (l *Logger) Warn(format string, args ...interface{}) {
	l.log(WarnLevel, format, args...)
}

// Error logs an error message
func (l *Logger) Error(format string, args ...interface{}) {
	l.log(ErrorLevel, format, args...)
}

// IncCounter increments a counter for observability
func (l *Logger) IncCounter(name string) {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.counters[name]++
}

// GetCounter returns the value of a counter
func (l *Logger) GetCounter(name string) int64 {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.counters[name]
}

// GetCounters returns all counters
func (l *Logger) GetCounters() map[string]int64 {
	l.mu.Lock()
	defer l.mu.Unlock()
	
	result := make(map[string]int64)
	for k, v := range l.counters {
		result[k] = v
	}
	return result
}

// ResetCounters resets all counters
func (l *Logger) ResetCounters() {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.counters = make(map[string]int64)
}

// WithPrefix creates a new logger with a prefix
func (l *Logger) WithPrefix(prefix string) *Logger {
	return &Logger{
		level:    l.level,
		format:   l.format,
		output:   l.output,
		prefix:   prefix,
		counters: l.counters,
	}
}

// Convenience functions using default logger
func Debug(format string, args ...interface{}) {
	GetLogger().Debug(format, args...)
}

func Info(format string, args ...interface{}) {
	GetLogger().Info(format, args...)
}

func Warn(format string, args ...interface{}) {
	GetLogger().Warn(format, args...)
}

func Error(format string, args ...interface{}) {
	GetLogger().Error(format, args...)
}

func Fatal(format string, args ...interface{}) {
	GetLogger().Error(format, args...)
	log.Fatalf(format, args...)
}
