import json
import boto3
from pathlib import Path
from slugify import slugify
from flask import current_app

class StorageService:
    @staticmethod
    def save_article_to_disk(article_obj, feed_name, reliability, feed_type=None):
        """
        Routes the save operation to either Local Disk or S3.
        """
        storage_type = current_app.config.get('STORAGE_TYPE', 'local').lower()
        file_content = StorageService._format_markdown(article_obj, feed_name, reliability, feed_type)
        entities_payload = StorageService._build_entities_payload(article_obj)

        # Define the structure: Source / Year / Month / Day / Title.md
        year = article_obj.pub_date.strftime("%Y")
        month = article_obj.pub_date.strftime("%m")
        day = article_obj.pub_date.strftime("%d")
        safe_source = slugify(feed_name)
        safe_basename = slugify(article_obj.title)
        safe_md_filename = f"{safe_basename}.md"
        sidecar_filename = f"{safe_basename}.entities.json"

        if storage_type == 's3':
            return StorageService._save_to_s3(
                safe_source,
                year,
                month,
                day,
                safe_md_filename,
                sidecar_filename,
                file_content,
                entities_payload,
            )
        else:
            return StorageService._save_to_local(
                safe_source,
                year,
                month,
                day,
                safe_md_filename,
                sidecar_filename,
                file_content,
                entities_payload,
            )

    @staticmethod
    def _save_to_local(
        safe_source, year, month, day, markdown_filename, sidecar_filename, content, entities
    ):
        vault_root = Path(current_app.config['VAULT_ROOT'])
        target_dir = vault_root / safe_source / year / month / day
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / markdown_filename
        sidecar_path = target_dir / sidecar_filename

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(entities, f, ensure_ascii=False, indent=2)

        return str(file_path)

    @staticmethod
    def _save_to_s3(
        safe_source,
        year,
        month,
        day,
        markdown_filename,
        sidecar_filename,
        content,
        entities,
    ):
        bucket_name = current_app.config.get('S3_BUCKET')
        if not bucket_name:
            raise ValueError("S3_BUCKET not configured")

        # Create S3 Key (Path) - Always use forward slashes for S3
        s3_markdown_key = f"{safe_source}/{year}/{month}/{day}/{markdown_filename}"
        s3_sidecar_key = f"{safe_source}/{year}/{month}/{day}/{sidecar_filename}"
        
        client_kwargs = {k: v for k, v in {
            'aws_access_key_id': current_app.config.get('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': current_app.config.get('AWS_SECRET_ACCESS_KEY'),
            'aws_session_token': current_app.config.get('AWS_SESSION_TOKEN'),
            'region_name': current_app.config.get('S3_REGION'),
        }.items() if v}

        s3 = boto3.client('s3', **client_kwargs)
        
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_markdown_key,
            Body=content.encode('utf-8'),
            ContentType='text/markdown'
        )

        s3.put_object(
            Bucket=bucket_name,
            Key=s3_sidecar_key,
            Body=json.dumps(entities).encode('utf-8'),
            ContentType='application/json'
        )

        return f"s3://{bucket_name}/{s3_markdown_key}"

    @staticmethod
    def _format_markdown(article, feed_name, reliability, feed_type):
        def yaml_list(csv_string):
            if not csv_string:
                return ""
            items = csv_string.split(',')
            return "\n".join([f"  - {item.strip()}" for item in items if item.strip()])

        md_output = f"""---
title: "{article.title}"
date: {article.pub_date.strftime('%Y-%m-%d %H:%M')}
added: {article.added_date.strftime('%Y-%m-%d %H:%M')}
source: "{feed_name}"
reliability: "{reliability}"
language: "{article.language}"
feed_type: "{feed_type or ''}"
tags:
{yaml_list(article.tags)}
organizations:
{yaml_list(article.organizations)}
people:
{yaml_list(article.people)}
locations:
{yaml_list(article.locations)}
events:
{yaml_list(article.events)}
link: {article.url}
---

# {article.title}

{article.content_edited}
"""
        if article.language != 'en' and article.content_original:
            md_output += f"""

---

## Original Text ({article.language.upper()})

{article.content_original}
"""
        return md_output

    @staticmethod
    def _build_entities_payload(article):
        return {
            'organizations': StorageService._csv_to_list(article.organizations),
            'people': StorageService._csv_to_list(article.people),
            'locations': StorageService._csv_to_list(article.locations),
            'events': StorageService._csv_to_list(article.events),
        }

    @staticmethod
    def _csv_to_list(csv_string):
        if not csv_string:
            return []
        return [item.strip() for item in csv_string.split(',') if item.strip()]