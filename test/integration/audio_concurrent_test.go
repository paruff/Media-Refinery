package integration_test

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/paruff/Media-Refinery/pkg/processor"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestConcurrent_WorkerPool tests worker pool behavior
func TestConcurrent_WorkerPool(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	ctx := context.Background()
	pool := processor.NewWorkerPool(4)
	defer pool.Close()

	var concurrent int32
	var maxConcurrent int32
	var mu sync.Mutex
	numTasks := 100
	var wg sync.WaitGroup

	results := make(map[int]bool)

	for i := 0; i < numTasks; i++ {
		i := i
		wg.Add(1)
		task := func() error {
			current := atomic.AddInt32(&concurrent, 1)
			mu.Lock()
			if current > atomic.LoadInt32(&maxConcurrent) {
				atomic.StoreInt32(&maxConcurrent, current)
			}
			mu.Unlock()
			time.Sleep(10 * time.Millisecond)
			mu.Lock()
			results[i] = true
			mu.Unlock()
			atomic.AddInt32(&concurrent, -1)
			wg.Done()
			return nil
		}
		require.NoError(t, pool.Submit(ctx, task))
	}

	wg.Wait()
	assert.Len(t, results, numTasks, "All tasks should complete")

	max := atomic.LoadInt32(&maxConcurrent)
	assert.Greater(t, max, int32(0), "Should have concurrent execution")
	assert.LessOrEqual(t, max, int32(4), "Should not exceed worker limit")
}

// TestConcurrent_RaceConditions is a lightweight check for races (run with -race)
func TestConcurrent_RaceConditions(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}
	// This test simply runs the worker pool under concurrent submissions to surface races when run with `-race`.
	ctx := context.Background()
	pool := processor.NewWorkerPool(8)
	defer pool.Close()

	var wg sync.WaitGroup
	for i := 0; i < 200; i++ {
		wg.Add(1)
		require.NoError(t, pool.Submit(ctx, func() error {
			time.Sleep(1 * time.Millisecond)
			wg.Done()
			return nil
		}))
	}
	wg.Wait()
}
