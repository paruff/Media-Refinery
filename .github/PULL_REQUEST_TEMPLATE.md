## Description
<!-- What does this PR do? -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation

## Safety invariants
Which `R-SAFE-*` (spec.md) does this touch? Write "none" if none.
- [ ] R-SAFE-1 originals never deleted/modified
- [ ] R-SAFE-2 write to `work/`, then atomic rename
- [ ] R-SAFE-3 generated paths sanitized, inside library root
- [ ] R-SAFE-4 dry-run writes nothing outside `work/dry-run/`
- [ ] R-SAFE-5 subprocess: arg list, timeout, stderr captured
- [ ] R-SAFE-6 API keys never logged or returned
- [ ] Based on `main` (not stacked on another PR)

## Testing
- [ ] All tests pass
- [ ] New tests added
- [ ] Coverage >85%

## Checklist
- [ ] Code follows style guide
- [ ] Type hints added
- [ ] Tests written BEFORE implementation (TDD)
- [ ] Async/await for I/O
- [ ] CHANGELOG.md updated
