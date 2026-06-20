package handler

import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"time"
)

var citationHTTP = &http.Client{Timeout: 15 * time.Second}

// SearchCitations queries CrossRef API and returns formatted citations.
// GET /api/citation/search?q=...
// No API key required — CrossRef is free and open.
func SearchCitations(w http.ResponseWriter, r *http.Request) {
	query := strings.TrimSpace(r.URL.Query().Get("q"))
	if query == "" {
		writeJSON(w, 400, "Parameter q diperlukan")
		return
	}
	if len(query) > 500 {
		query = query[:500]
	}

	results, err := QueryCrossRef(query)
	if err != nil {
		slog.Error("crossref query", "error", err)
		writeJSON(w, 500, "Gagal mencari referensi. Coba lagi.")
		return
	}

	writeJSON(w, 200, map[string]interface{}{
		"query":   query,
		"count":   len(results),
		"results": results,
	})
}

type citationResult struct {
	Title     string `json:"title"`
	Authors   string `json:"authors"`
	Year      int    `json:"year"`
	Journal   string `json:"journal"`
	DOI       string `json:"doi"`
	CiteCount int    `json:"cite_count"`
	URL       string `json:"url"`
	APA       string `json:"apa"`
}

func QueryCrossRef(query string) ([]citationResult, error) {
	u := fmt.Sprintf("https://api.crossref.org/works?query=%s&rows=5&sort=relevance",
		url.QueryEscape(query))

	req, err := http.NewRequest("GET", u, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "TokenLine/1.0 (mailto:support@tokenline.top)")

	resp, err := citationHTTP.Do(req)
	if err != nil {
		return nil, fmt.Errorf("crossref http: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("crossref status %d", resp.StatusCode)
	}

	var data struct {
		Message struct {
			Items []struct {
				Title  []string `json:"title"`
				Author []struct {
					Family string `json:"family"`
				} `json:"author"`
				Created struct {
					DateParts [][]int `json:"date-parts"`
				} `json:"created"`
				ContainerTitle      []string `json:"container-title"`
				DOI                 string   `json:"DOI"`
				IsReferencedByCount int      `json:"is-referenced-by-count"`
				URL                 string   `json:"URL"`
			} `json:"items"`
		} `json:"message"`
	}
	if err := json.Unmarshal(body, &data); err != nil {
		return nil, fmt.Errorf("crossref parse: %w", err)
	}

	var results []citationResult
	for _, item := range data.Message.Items {
		title := ""
		if len(item.Title) > 0 {
			title = item.Title[0]
		}
		authors := make([]string, 0, len(item.Author))
		for _, a := range item.Author {
			if a.Family != "" {
				authors = append(authors, a.Family)
			}
		}
		authorStr := strings.Join(authors, ", ")
		if len(authors) > 3 {
			authorStr = authors[0] + " et al."
		}

		year := 0
		if len(item.Created.DateParts) > 0 && len(item.Created.DateParts[0]) > 0 {
			year = item.Created.DateParts[0][0]
		}

		journal := ""
		if len(item.ContainerTitle) > 0 {
			journal = item.ContainerTitle[0]
		}

		doiURL := item.URL
		if doiURL == "" && item.DOI != "" {
			doiURL = "https://doi.org/" + item.DOI
		}

		// Format APA 7th: Author. (Year). Title. Journal. DOI
		apa := ""
		if authorStr != "" && year > 0 && title != "" {
			apa = fmt.Sprintf("%s (%d). %s.", authorStr, year, title)
			if journal != "" {
				apa += fmt.Sprintf(" %s.", journal)
			}
			if item.DOI != "" {
				apa += fmt.Sprintf(" https://doi.org/%s", item.DOI)
			}
		}

		results = append(results, citationResult{
			Title:     title,
			Authors:   authorStr,
			Year:      year,
			Journal:   journal,
			DOI:       item.DOI,
			CiteCount: item.IsReferencedByCount,
			URL:       doiURL,
			APA:       apa,
		})
	}
	return results, nil
}
