package main

import (
	"encoding/json"
	"fmt"
	"os"
)

// Metadata contract
type TaskMetadata struct {
	TaskID   string `json:"task_id"`
	SHMName  string `json:"shm_name"`
	Size     int    `json:"payload_size"`
}

func main() {
	var meta TaskMetadata
	decoder := json.NewDecoder(os.Stdin)
	if err := decoder.Decode(&meta); err != nil {
		fmt.Fprintf(os.Stderr, "Error decodificando metadatos: %v\n", err)
		os.Exit(1)
	}

	// Lógica de procesamiento masivo en Go
	fmt.Fprintf(os.Stdout, `{"status": "processing", "worker": "go_concurrency_v1", "task": "%s"}`, meta.TaskID)
}
