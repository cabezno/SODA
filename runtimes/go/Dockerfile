# Runtime para Go
FROM golang:1.21-alpine

WORKDIR /app

RUN apk add --no-cache git make build-base

# Instalar herramientas de linting y testeo
RUN go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest && \
    go install github.com/rakyll/gotest@latest

CMD ["go"]
