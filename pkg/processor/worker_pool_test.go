package processor
package processor_test

import (
    "context"
    "errors"
    "sync/atomic"
    "testing"
    "time"

    "github.com/paruff/media-refinery/pkg/processor"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)
















































































}    assert.NotEmpty(t, errs, "Should report cancellation")    errs := pool.WaitWithErrors()    cancel()    require.NoError(t, err)    err = pool.Submit(ctx, task)    }        return nil        time.Sleep(5 * time.Second)    task := func() error {    ctx, cancel := context.WithCancel(context.Background())    defer pool.Close()    require.NoError(t, err)    pool, err := processor.NewWorkerPool(2)func TestWorkerPool_ContextCancellation(t *testing.T) {// TestWorkerPool_ContextCancellation tests cancellation}    assert.Contains(t, errs, expectedErr, "Should contain task error")    assert.NotEmpty(t, errs, "Should collect errors")    errs := pool.WaitWithErrors()    require.NoError(t, err)    err = pool.Submit(ctx, task)    }        return expectedErr    task := func() error {    expectedErr := errors.New("task failed")    ctx := context.Background()    defer pool.Close()    require.NoError(t, err)    pool, err := processor.NewWorkerPool(2)func TestWorkerPool_ErrorHandling(t *testing.T) {// TestWorkerPool_ErrorHandling tests error propagation}    assert.Equal(t, int32(10), atomic.LoadInt32(&executed))    pool.Wait()    }        require.NoError(t, err)        err := pool.Submit(ctx, task)    for i := 0; i < 10; i++ {    }        return nil        atomic.AddInt32(&executed, 1)    task := func() error {    var executed int32    ctx := context.Background()    defer pool.Close()    require.NoError(t, err)    pool, err := processor.NewWorkerPool(2)func TestWorkerPool_TaskExecution(t *testing.T) {// TestWorkerPool_TaskExecution tests task execution}    }        })            pool.Close()            assert.NotNil(t, pool)            require.NoError(t, err)            }                return                assert.Error(t, err)            if tt.wantErr {            pool, err := processor.NewWorkerPool(tt.workers)        t.Run(tt.name, func(t *testing.T) {    for _, tt := range tests {    }        {"Negative workers", -1, true},        {"Zero workers", 0, true},        {"Max workers", 16, false},        {"Single worker", 1, false},        {"Valid pool size", 4, false},    }{        wantErr bool        workers int        name    string    tests := []struct {func TestWorkerPool_Creation(t *testing.T) {// TestWorkerPool_Creation tests pool creation