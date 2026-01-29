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

    var concurrent int32
    var maxConcurrent int32
    var mu sync.Mutex
    numTasks := 20
    var wg sync.WaitGroup

    for i := 0; i < numTasks; i++ {
        wg.Add(1)
        task := func() error {
            current := atomic.AddInt32(&concurrent, 1)
            mu.Lock()
            if current > atomic.LoadInt32(&maxConcurrent) {
                atomic.StoreInt32(&maxConcurrent, current)
            }
            mu.Unlock()
            time.Sleep(50 * time.Millisecond)
            atomic.AddInt32(&concurrent, -1)







































}    assert.Len(t, results, 100, "All tasks should complete")    wg.Wait()    }        require.NoError(t, pool.Submit(ctx, task))        }            return nil            wg.Done()            mu.Unlock()            results[taskID] = true            mu.Lock()        task := func() error {        taskID := i        wg.Add(1)    for i := 0; i < 100; i++ {    var wg sync.WaitGroup    var mu sync.Mutex    results := make(map[int]bool)    defer pool.Close()    pool := processor.NewWorkerPool(4)    ctx := context.Background()func TestConcurrent_RaceConditions(t *testing.T) {// TestConcurrent_RaceConditions tests for race conditions}    assert.Greater(t, max, int32(0), "Should have concurrent execution")    assert.LessOrEqual(t, max, int32(4), "Should not exceed worker limit")    max := atomic.LoadInt32(&maxConcurrent)    pool.Close()    wg.Wait()    }        require.NoError(t, err)        err := pool.Submit(ctx, task)        }            return nil            wg.Done()