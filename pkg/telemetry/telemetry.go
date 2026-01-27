package telemetry

import (
	"context"
	"fmt"
	"os"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetrichttp"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/metric"
	"go.opentelemetry.io/otel/propagation"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
	"go.opentelemetry.io/otel/trace"
)

// Provider manages OpenTelemetry tracing and metrics
type Provider struct {
	tracerProvider *sdktrace.TracerProvider
	meterProvider  *sdkmetric.MeterProvider
	tracer         trace.Tracer
	meter          metric.Meter
	
	// Metrics
	filesProcessedCounter metric.Int64Counter
	filesFailedCounter    metric.Int64Counter
	processingDuration    metric.Float64Histogram
	fileSizeHistogram     metric.Int64Histogram
	conversionDuration    metric.Float64Histogram
}

// Initialize sets up OpenTelemetry with OTLP exporters
func Initialize(ctx context.Context, serviceName, serviceVersion string) (*Provider, error) {
	// Create resource with service information
	res, err := resource.Merge(
		resource.Default(),
		resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName(serviceName),
			semconv.ServiceVersion(serviceVersion),
			attribute.String("environment", getEnv("ENVIRONMENT", "production")),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create resource: %w", err)
	}

	// Setup trace exporter
	traceExporter, err := otlptracehttp.New(ctx,
		otlptracehttp.WithEndpoint(getOTLPEndpoint()),
		otlptracehttp.WithInsecure(), // Using plain HTTP
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create trace exporter: %w", err)
	}

	// Setup trace provider
	tracerProvider := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(traceExporter),
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)
	otel.SetTracerProvider(tracerProvider)
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	// Setup metric exporter
	metricExporter, err := otlpmetrichttp.New(ctx,
		otlpmetrichttp.WithEndpoint(getOTLPEndpoint()),
		otlpmetrichttp.WithInsecure(),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create metric exporter: %w", err)
	}

	// Setup metric provider
	meterProvider := sdkmetric.NewMeterProvider(
		sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter,
			sdkmetric.WithInterval(10*time.Second))),
		sdkmetric.WithResource(res),
	)
	otel.SetMeterProvider(meterProvider)

	// Create tracer and meter
	tracer := otel.Tracer(serviceName)
	meter := otel.Meter(serviceName)

	// Initialize metrics
	filesProcessedCounter, err := meter.Int64Counter(
		"media.files.processed",
		metric.WithDescription("Total number of files processed successfully"),
		metric.WithUnit("{file}"),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create files processed counter: %w", err)
	}

	filesFailedCounter, err := meter.Int64Counter(
		"media.files.failed",
		metric.WithDescription("Total number of files that failed processing"),
		metric.WithUnit("{file}"),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create files failed counter: %w", err)
	}

	processingDuration, err := meter.Float64Histogram(
		"media.processing.duration",
		metric.WithDescription("Duration of file processing operations"),
		metric.WithUnit("s"),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create processing duration histogram: %w", err)
	}

	fileSizeHistogram, err := meter.Int64Histogram(
		"media.file.size",
		metric.WithDescription("Size of processed files"),
		metric.WithUnit("By"),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create file size histogram: %w", err)
	}

	conversionDuration, err := meter.Float64Histogram(
		"media.conversion.duration",
		metric.WithDescription("Duration of media conversion operations"),
		metric.WithUnit("s"),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create conversion duration histogram: %w", err)
	}

	return &Provider{
		tracerProvider:        tracerProvider,
		meterProvider:         meterProvider,
		tracer:                tracer,
		meter:                 meter,
		filesProcessedCounter: filesProcessedCounter,
		filesFailedCounter:    filesFailedCounter,
		processingDuration:    processingDuration,
		fileSizeHistogram:     fileSizeHistogram,
		conversionDuration:    conversionDuration,
	}, nil
}

// Shutdown cleanly shuts down the telemetry providers
func (p *Provider) Shutdown(ctx context.Context) error {
	var err error
	if p.tracerProvider != nil {
		if shutdownErr := p.tracerProvider.Shutdown(ctx); shutdownErr != nil {
			err = fmt.Errorf("tracer provider shutdown failed: %w", shutdownErr)
		}
	}
	if p.meterProvider != nil {
		if shutdownErr := p.meterProvider.Shutdown(ctx); shutdownErr != nil {
			if err != nil {
				err = fmt.Errorf("%v; meter provider shutdown failed: %w", err, shutdownErr)
			} else {
				err = fmt.Errorf("meter provider shutdown failed: %w", shutdownErr)
			}
		}
	}
	return err
}

// StartSpan creates a new span with the given name
func (p *Provider) StartSpan(ctx context.Context, name string, attrs ...attribute.KeyValue) (context.Context, trace.Span) {
	return p.tracer.Start(ctx, name, trace.WithAttributes(attrs...))
}

// RecordFileProcessed records a successfully processed file
func (p *Provider) RecordFileProcessed(ctx context.Context, fileType, format string, fileSize int64) {
	attrs := metric.WithAttributes(
		attribute.String("file.type", fileType),
		attribute.String("file.format", format),
	)
	p.filesProcessedCounter.Add(ctx, 1, attrs)
	p.fileSizeHistogram.Record(ctx, fileSize, attrs)
}

// RecordFileFailed records a failed file processing
func (p *Provider) RecordFileFailed(ctx context.Context, fileType string, errorType string) {
	p.filesFailedCounter.Add(ctx, 1, metric.WithAttributes(
		attribute.String("file.type", fileType),
		attribute.String("error.type", errorType),
	))
}

// RecordProcessingDuration records the duration of a processing operation
func (p *Provider) RecordProcessingDuration(ctx context.Context, duration time.Duration, fileType string, success bool) {
	p.processingDuration.Record(ctx, duration.Seconds(), metric.WithAttributes(
		attribute.String("file.type", fileType),
		attribute.Bool("success", success),
	))
}

// RecordConversionDuration records the duration of a conversion operation
func (p *Provider) RecordConversionDuration(ctx context.Context, duration time.Duration, inputFormat, outputFormat string) {
	p.conversionDuration.Record(ctx, duration.Seconds(), metric.WithAttributes(
		attribute.String("input.format", inputFormat),
		attribute.String("output.format", outputFormat),
	))
}

// getOTLPEndpoint returns the OTLP endpoint from environment
func getOTLPEndpoint() string {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "localhost:4318"
	}
	// Remove http:// or https:// prefix if present
	endpoint = trimProtocol(endpoint)
	return endpoint
}

// trimProtocol removes http:// or https:// prefix
func trimProtocol(endpoint string) string {
	if len(endpoint) > 7 && endpoint[:7] == "http://" {
		return endpoint[7:]
	}
	if len(endpoint) > 8 && endpoint[:8] == "https://" {
		return endpoint[8:]
	}
	return endpoint
}

// getEnv gets an environment variable with a default value
func getEnv(key, defaultValue string) string {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	return value
}
