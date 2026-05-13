package git

import "errors"

// ErrNoGitRepos indicates DetectRepos found no .git directory at the base
// path or one level below.
var ErrNoGitRepos = errors.New("no .git directory at path or one level below")
