package processor
package processor

import (
    "context"
    "errors"
    "sync"
)

type TaskFunc func() error

type WorkerPool struct {
    tasks      chan TaskFunc
    wg         sync.WaitGroup
    closeOnce  sync.Once
    closeCh    chan struct{}
    errorsMu   sync.Mutex
    errors     []error
}

// NewWorkerPool creates a new worker pool with n workers
func NewWorkerPool(n int) (*WorkerPool, error) {
    if n < 1 {
        return nil, errors.New("worker count must be >= 1")
    }
    pool := &WorkerPool{
        tasks:   make(chan TaskFunc),
        closeCh: make(chan struct{}),
    }
    for i := 0; i < n; i++ {
        pool.wg.Add(1)
        go pool.worker()
    }
    return pool, nil
}

// Submit submits a task to the pool
func (p *WorkerPool) Submit(ctx context.Context, task TaskFunc) error {
    select {
    case <-ctx.Done():
        return ctx.Err()
    case <-p.closeCh:
        return errors.New("worker pool closed")
    case p.tasks <- task:
        return nil
    }
}

// Wait waits for all tasks to complete
func (p *WorkerPool) Wait() {
    p.Close()
    p.wg.Wait()
}

// WaitWithErrors waits and returns all errors
func (p *WorkerPool) WaitWithErrors() []error {
    p.Close()
    p.wg.Wait()
    p.errorsMu.Lock()
    defer p.errorsMu.Unlock()
    return append([]error(nil), p.errors...)
}

// Close closes the pool for new tasks
func (p *WorkerPool) Close() {
    p.closeOnce.Do(func() {
        close(p.closeCh)
        close(p.tasks)
    })
}

func (p *WorkerPool) worker() {
    defer p.wg.Done()
    for task := range p.tasks {
        if err := task(); err != nil {
            p.errorsMu.Lock()
            p.errors = append(p.errors, err)
            p.errorsMu.Unlock()
        }
    }
}
