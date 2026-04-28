## Skill: Go

You are building a Go application. Follow these conventions:

- Go 1.21+; use Go modules (`go.mod` + `go.sum`)
- Idiomatic error handling: always check errors, return `error` as last return value
- Use Gin framework for REST APIs: `github.com/gin-gonic/gin`
- Package structure: `cmd/` (entry points), `internal/` (private packages), `pkg/` (public packages)
- Handler functions receive `*gin.Context`; bind JSON with `c.ShouldBindJSON(&dto)`
- Use interfaces for dependencies — enables testing with mocks
- GORM for ORM: `gorm.io/gorm` with the appropriate driver
- `go.mod` with all dependencies declared; run `go mod tidy` after changes
- Run with: `go run cmd/main.go` or `go build ./...`
- Never use `panic` in business logic; return errors instead
