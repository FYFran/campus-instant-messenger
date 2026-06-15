"""Tighten rate limits on auth endpoints."""
with open("/app/rewriter-go/main.go") as f:
    content = f.read()

# Reduce auth rate from 3/sec burst 5 → 2/sec burst 3
content = content.replace(
    'authLimiter := middleware.NewRateLimiter(3, 5)',
    'authLimiter := middleware.NewRateLimiter(2, 3)'
)

with open("/app/rewriter-go/main.go", "w") as f:
    f.write(content)
print("DONE")
