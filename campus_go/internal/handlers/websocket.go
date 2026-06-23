package handlers

import (
	log "campus-go/internal/logger"
	"encoding/json"
	"net/http"
	"sync"

	"campus-go/internal/middleware"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// WSClient represents a connected WebSocket client
type WSClient struct {
	conn   *websocket.Conn
	send   chan []byte
	userID int
	role   string
}

// WSHub manages all WebSocket connections
type WSHub struct {
	clients    map[*WSClient]bool
	broadcast  chan []byte
	register   chan *WSClient
	unregister chan *WSClient
	mu         sync.RWMutex
}

var Hub = &WSHub{
	clients:    make(map[*WSClient]bool),
	broadcast:  make(chan []byte, 256),
	register:   make(chan *WSClient),
	unregister: make(chan *WSClient),
}

func (h *WSHub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
			}
			h.mu.Unlock()
		case msg := <-h.broadcast:
			h.mu.RLock()
			for client := range h.clients {
				select {
				case client.send <- msg:
				default:
					close(client.send)
					delete(h.clients, client)
				}
			}
			h.mu.RUnlock()
		}
	}
}

// Broadcast sends a JSON message to all connected clients
func Broadcast(eventType string, payload interface{}) {
	data, _ := json.Marshal(map[string]interface{}{
		"type": eventType,
		"data": payload,
	})
	Hub.broadcast <- data
}

// HandleWS — GET /api/ws
func HandleWS(c *gin.Context) {
	token := c.Query("token")
	if token == "" {
		c.JSON(401, gin.H{"detail": "缺少token"})
		return
	}

	claims, err := middleware.ParseToken(token)
	if err != nil {
		c.JSON(401, gin.H{"detail": "Token无效"})
		return
	}

	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return
	}

	client := &WSClient{
		conn:   conn,
		send:   make(chan []byte, 64),
		userID: claims.UserID,
		role:   claims.Role,
	}
	Hub.register <- client

	go client.writePump()
	go client.readPump()
}

func (c *WSClient) writePump() {
	defer c.conn.Close()
	for msg := range c.send {
		if err := c.conn.WriteMessage(websocket.TextMessage, msg); err != nil {
			return
		}
	}
}

func (c *WSClient) readPump() {
	defer func() {
		Hub.unregister <- c
		c.conn.Close()
	}()
	for {
		_, _, err := c.conn.ReadMessage()
		if err != nil {
			break
		}
	}
}
