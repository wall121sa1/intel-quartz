import os
from pathlib import Path
from slugify import slugify
from flask import current_app

class StorageService:
    @staticmethod
    def save_article_to_disk(article_obj, feed_name, reliability):
        """
        Writes a database Article object to the filesystem.
        """
        vault_root = Path(current_app.config['VAULT_ROOT'])
        
        # Date based folder structure
        year = article_obj.pub_date.strftime("%Y")
        month = article_obj.pub_date.strftime("%m")
        day = article_obj.pub_date.strftime("%d")
        
        # Paths
        safe_source = slugify(feed_name)
        target_dir = vault_root / safe_source / year / month / day
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = f"{slugify(article_obj.title)}.md"
        file_path = target_dir / safe_filename

        # Generate Content
        file_content = StorageService._format_markdown(article_obj, feed_name, reliability)

        # Write
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)
        
        return str(file_path)

    @staticmethod
    def _format_markdown(article, feed_name, reliability):
        # Helper for YAML lists
        def yaml_list(csv_string):
            if not csv_string:
                return ""
            items = csv_string.split(',')
            return "\n".join([f"  - {item.strip()}" for item in items if item.strip()])

        return f"""---
title: "{article.title}"
date: {article.pub_date.strftime('%Y-%m-%d %H:%M')}
added: {article.added_date.strftime('%Y-%m-%d %H:%M')}
source: "{feed_name}"
reliability: "{reliability}"
organizations:
{yaml_list(article.organizations)}
people:
{yaml_list(article.people)}
locations:
{yaml_list(article.locations)}
link: {article.url}
---

# {article.title}

{article.content_edited}
"""