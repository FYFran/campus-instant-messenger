"""Customize KA-Launchly CSS for TokenLine brand"""
import re

with open(r'f:/ClaudeFiles/_research/ka-template/assets/css/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

# CSS variable changes
css = css.replace('--bg: 248 250 252;', '--bg: 250 249 246;')
css = css.replace('--fg: 15 23 42;', '--fg: 26 27 44;')
css = css.replace('--muted: 71 85 105;', '--muted: 100 100 120;')
css = css.replace('--surface-soft: 241 245 249;', '--surface-soft: 245 244 241;')
css = css.replace('--primary: 99 102 241;', '--primary: 26 27 44;')
css = css.replace('--secondary: 139 92 246;', '--secondary: 184 151 90;')
css = css.replace('--accent: 6 182 212;', '--accent: 184 151 90;')

# Replace indigo/purple/cyan → TokenLine dark/gold
css = re.sub(r'rgba\(99, *102, *241', 'rgba(26, 27, 44', css)
css = re.sub(r'rgba\(139, *92, *246', 'rgba(184, 151, 90', css)
css = re.sub(r'rgba\(6, *182, *212', 'rgba(184, 151, 90', css)
css = re.sub(r'rgb\(99, *102, *241\)', 'rgb(26, 27, 44)', css)
css = re.sub(r'rgb\(139, *92, *246\)', 'rgb(184, 151, 90)', css)
css = re.sub(r'rgb\(6, *182, *212\)', 'rgb(184, 151, 90)', css)

# Font
css = css.replace('"Plus Jakarta Sans", "Inter", sans-serif', '"Inter", system-ui, sans-serif')

with open(r'f:/ClaudeFiles/_research/ka-template/assets/css/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
print("CSS done")
