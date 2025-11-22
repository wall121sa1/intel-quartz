import os
from pathlib import Path
from slugify import slugify
from watcher.app.models import ArticleData

class ObsidianStorage:
    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root)

    def save_article(self, article: ArticleData):
        year = article.published_date.strftime("%Y")
        month = article.published_date.strftime("%m")
        day = article.published_date.strftime("%d")
        
        safe_source = slugify(article.source_name)
        target_dir = self.vault_root / safe_source / year / month / day
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = f"{slugify(article.title)}.md"
        file_path = target_dir / safe_filename

        content = self._format_content(article)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"Saved: {file_path}")

    def _format_content(self, article: ArticleData) -> str:
        # Helper for standard YAML lists (No brackets)
        def yaml_list(items):
            if not items:
                return ""
            # Returns: 
            #   - New York
            #   - London
            return "\n".join([f"  - {item}" for item in items])

        return f"""---
title: "{article.title}"
date: {article.published_date.strftime('%Y-%m-%d %H:%M')}
added: {article.added_date.strftime('%Y-%m-%d %H:%M')}
source: "{article.source_name}"
reliability: "{article.source_reliability}"
organizations:
{yaml_list(article.organizations)}
people:
{yaml_list(article.people)}
locations:
{yaml_list(article.locations)}
link: {article.url}
---

# {article.title}

{article.content}
"""