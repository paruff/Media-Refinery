package processor_test

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"

	"github.com/paruff/Media-Refinery/pkg/processor"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestWorkerPool_Creation(t *testing.T) {
	tests := []struct {
		name    string
		workers int
		wantErr bool
	}{
		{"Valid pool size", 4, false},
		{"Single worker", 1, false},
		{"Max workers", 16, false},
		{"Zero workers", 0, true},
		{"Negative workers", -1, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			pool, err := processor.NewWorkerPool(tt.workers)
			if tt.wantErr {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
				assert.NotNil(t, pool)
				pool.Close()
			}
		})
	}
}

func TestWorkerPool_TaskExecution(t *testing.T) {
	pool, err := processor.NewWorkerPool(2)
	require.NoError(t, err)
	defer pool.Close()

	var executed int32
	task := func() error {
		atomic.AddInt32(&executed, 1)
		return nil
	}
	ctx := context.Background()
	for i := 0; i < 10; i++ {
		require.NoError(t, pool.Submit(ctx, task))
	}
	pool.Wait()
	assert.Equal(t, int32(10), atomic.LoadInt32(&executed))
}

func TestWorkerPool_ErrorHandling(t *testing.T) {
	pool, err := processor.NewWorkerPool(2)
	require.NoError(t, err)
	defer pool.Close()

	expectedErr := errors.New("task failed")
	task := func() error {
		return expectedErr
	}
	ctx := context.Background()
	require.NoError(t, pool.Submit(ctx, task))
	errs := pool.WaitWithErrors()
	assert.NotEmpty(t, errs, "Should collect errors")
	assert.Contains(t, errs, expectedErr, "Should contain task error")
}

func TestWorkerPool_ContextCancellation(t *testing.T) {
	pool, err := processor.NewWorkerPool(2)
	require.NoError(t, err)
	defer pool.Close()

	task := func() error {
		time.Sleep(5 * time.Second)
		return nil
	}
	ctx, cancel := context.WithCancel(context.Background())
	require.NoError(t, pool.Submit(ctx, task))
	cancel()
	errs := pool.WaitWithErrors()
	assert.NotEmpty(t, errs, "Should report cancellation")
}
