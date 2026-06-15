"""Add missing routes to server main.go"""
with open("/app/rewriter-go/main.go") as f:
    content = f.read()

has_balance = "me/balance" in content
has_packs = "/api/packs" in content
print(f"balance route: {has_balance}, packs route: {has_packs}")

if not has_balance:
    content = content.replace(
        'mux.HandleFunc("GET /api/me", chain(userH.Me, middleware.Auth(cfg.JWTSecret)))',
        'mux.HandleFunc("GET /api/me", chain(userH.Me, middleware.Auth(cfg.JWTSecret)))\n\tmux.HandleFunc("GET /api/me/balance", chain(chatH.GetBalance, middleware.Auth(cfg.JWTSecret)))'
    )

if not has_packs:
    content = content.replace(
        'mux.HandleFunc("GET /api/me/stats"',
        'mux.HandleFunc("GET /api/packs", payH.ListPacks)\n\tmux.HandleFunc("GET /api/me/stats"'
    )

with open("/app/rewriter-go/main.go", "w") as f:
    f.write(content)
print("DONE")
