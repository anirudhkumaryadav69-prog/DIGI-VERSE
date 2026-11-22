"""Idempotent demo digital marketplace catalog & storefront seeder.

Strict safety guarantees:
- Allows execution ONLY in development/local environments against localhost `digiverse_local`
  (or `digiverse_test` exclusively when explicitly authorized by the automated test suite).
- Inspects BOTH settings/URL and active PostgreSQL `SELECT current_database()` before writing.
- Explicitly rejects `digiverse`, production, staging, remote hosts, and unknown databases.
- Never truncates, drops, or modifies existing customer, admin, order, payment, or product rows.
- Creates genuine valid binary downloadable files (PDF, ZIP, CSV, JSON, MD, WAV) stored via
  `validate_and_spool_asset_upload` + `get_asset_storage().save(...)` (private storage only).
- Creates 96 unique 640x400 PNG product images (32 primary + 64 gallery previews) stored via
  `get_image_storage().save_image(...)` cleanly synchronized with `Product.image_url`.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import secrets
import struct
import sys
import uuid
import wave
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from starlette.datastructures import Headers, UploadFile

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.catalog import Category, Product, ProductImage, Sale
from app.models.customer import Customer
from app.models.enums import AccountStatus, ProductApprovalStatus, SellerApplicationStatus
from app.models.seller import SellerProfile
from app.services.asset_storage_service import get_asset_storage, validate_and_spool_asset_upload
from app.services.catalog_service import replace_product_image, upload_product_image

DEMO_DISCLAIMER = "DEMO SAMPLE — FOR PREVIEW AND TESTING ONLY"
DEMO_DISCOUNT_DURATION_DAYS = 90
LOCAL_ALLOWED_ENVS = {"development", "dev", "local"}
TEST_ALLOWED_ENVS = {"development", "dev", "local", "test", "testing"}
ALLOWED_LOCAL_HOSTS = {"localhost", "127.0.0.1"}


@dataclass(frozen=True)
class DemoSellerSpec:
    store_slug: str
    store_name: str
    seller_display_name: str
    email: str
    country: str
    business_type: str
    categories: list[str]
    tagline: str


@dataclass(frozen=True)
class DemoCategorySpec:
    slug: str
    name: str
    description: str
    palette: tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]


@dataclass(frozen=True)
class DemoProductSpec:
    slug: str
    name: str
    category_slug: str
    seller_slug: Optional[str]
    original_price: Decimal
    sale_price: Optional[Decimal]
    product_type: str
    asset_ext: str
    asset_mime: str
    short_description: str
    main_description: str
    detailed_description: str
    tags: list[str]
    includes: list[str]


@dataclass
class SeedStats:
    database_name: str
    sellers_created: int = 0
    sellers_existing: int = 0
    categories_created: int = 0
    categories_existing: int = 0
    products_created: int = 0
    products_updated: int = 0
    products_existing: int = 0
    sales_created: int = 0
    assets_uploaded: int = 0
    assets_skipped: int = 0
    images_uploaded: int = 0
    images_skipped: int = 0
    image_hashes: set[str] = field(default_factory=set)

    def summary_dict(self) -> dict[str, Any]:
        return {
            "database": self.database_name,
            "sellers_created": self.sellers_created,
            "sellers_existing": self.sellers_existing,
            "categories_created": self.categories_created,
            "categories_existing": self.categories_existing,
            "products_created": self.products_created,
            "products_updated": self.products_updated,
            "products_existing": self.products_existing,
            "sales_created": self.sales_created,
            "assets_uploaded": self.assets_uploaded,
            "assets_skipped": self.assets_skipped,
            "images_uploaded": self.images_uploaded,
            "images_skipped": self.images_skipped,
            "unique_image_hashes_in_run": len(self.image_hashes),
        }


DEMO_SELLERS: tuple[DemoSellerSpec, ...] = (
    DemoSellerSpec(
        store_slug="demo-pixelcraft-studio",
        store_name="PixelCraft Studio",
        seller_display_name="PixelCraft Studio",
        email="pixelcraft-studio@demo.digiverse.local",
        country="India",
        business_type="Digital Creator Studio",
        categories=["Design & Graphics", "AI Resources & Automation", "Digital Marketing", "Audio & Video"],
        tagline="Synthetic UI kits, social design systems, and multimedia presets.",
    ),
    DemoSellerSpec(
        store_slug="demo-codeforge-labs",
        store_name="CodeForge Labs",
        seller_display_name="CodeForge Labs",
        email="codeforge-labs@demo.digiverse.local",
        country="India",
        business_type="Software Starter Lab",
        categories=["Development & Technology", "AI Resources & Automation", "Digital Marketing", "Audio & Video"],
        tagline="Synthetic frontend starters, Python automation kits, and motion templates.",
    ),
    DemoSellerSpec(
        store_slug="demo-learnvault-academy",
        store_name="LearnVault Academy",
        seller_display_name="LearnVault Academy",
        email="learnvault-academy@demo.digiverse.local",
        country="India",
        business_type="Educational Publisher",
        categories=["Education & Learning", "AI Resources & Automation", "Digital Marketing", "Audio & Video"],
        tagline="Synthetic programming handbooks, DSA notes, and creator study guides.",
    ),
    DemoSellerSpec(
        store_slug="demo-bizflow-collective",
        store_name="BizFlow Collective",
        seller_display_name="BizFlow Collective",
        email="bizflow-collective@demo.digiverse.local",
        country="India",
        business_type="Business Templates Collective",
        categories=["Documents & Productivity", "Business Resources"],
        tagline="Synthetic business planning workbooks, Notion dashboards, and financial models.",
    ),
)

DEMO_CATEGORIES: tuple[DemoCategorySpec, ...] = (
    DemoCategorySpec(
        slug="design-and-graphics",
        name="Design & Graphics",
        description="Professional design resources, creative assets, templates, illustrations, and UI resources.",
        palette=((245, 243, 255), (124, 58, 237), (30, 27, 75)),
    ),
    DemoCategorySpec(
        slug="documents-and-productivity",
        name="Documents & Productivity",
        description="Digital templates that improve productivity, organization, and everyday workflows.",
        palette=((239, 246, 255), (37, 99, 235), (15, 23, 42)),
    ),
    DemoCategorySpec(
        slug="education-and-learning",
        name="Education & Learning",
        description="Educational resources, programming guides, learning materials, and study resources.",
        palette=((240, 253, 244), (22, 163, 74), (20, 45, 35)),
    ),
    DemoCategorySpec(
        slug="development-and-technology",
        name="Development & Technology",
        description="Developer resources, source code, website templates, scripts, and reusable components.",
        palette=((238, 242, 255), (79, 70, 229), (15, 23, 42)),
    ),
    DemoCategorySpec(
        slug="ai-resources-and-automation",
        name="AI Resources & Automation",
        description="AI prompts, workflow templates, automation resources, and AI productivity tools.",
        palette=((236, 254, 255), (8, 145, 178), (15, 23, 42)),
    ),
    DemoCategorySpec(
        slug="digital-marketing",
        name="Digital Marketing",
        description="Resources for social media management, branding, marketing campaigns, and content creation.",
        palette=((255, 241, 242), (244, 63, 94), (31, 41, 55)),
    ),
    DemoCategorySpec(
        slug="audio-and-video",
        name="Audio & Video",
        description="Digital multimedia resources, editing templates, sound effects, and creative assets.",
        palette=((255, 251, 235), (217, 119, 6), (31, 41, 55)),
    ),
    DemoCategorySpec(
        slug="business-resources",
        name="Business Resources",
        description="Business planning resources, startup templates, financial models, and professional presentations.",
        palette=((240, 253, 250), (13, 148, 136), (15, 23, 42)),
    ),
)

DEMO_PRODUCTS: tuple[DemoProductSpec, ...] = (
    # 1. Design & Graphics
    DemoProductSpec(
        slug="demo-modern-social-media-kit",
        name="Modern Social Media Kit",
        category_slug="design-and-graphics",
        seller_slug="demo-pixelcraft-studio",
        original_price=Decimal("299.00"),
        sale_price=Decimal("199.00"),
        product_type="Design Templates",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="30 editable social media template layouts, color tokens, and typography specs.",
        main_description="Structured social media campaign kit covering square feed, story frames, and carousel grids.",
        detailed_description=f"{DEMO_DISCLAIMER}. Includes layered SVG layout blueprints, color token JSON, and grid guidelines packaged in a verified ZIP bundle.",
        tags=["social-media", "templates", "design-system", "demo"],
        includes=["README.md", "30 layout blueprints", "brand-tokens.json"],
    ),
    DemoProductSpec(
        slug="demo-minimal-portfolio-ui-kit",
        name="Minimal Portfolio UI Kit",
        category_slug="design-and-graphics",
        seller_slug="demo-pixelcraft-studio",
        original_price=Decimal("449.00"),
        sale_price=None,
        product_type="UI Kit",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Personal portfolio interface design resources with clean typographic scales and grid tokens.",
        main_description="Reusable portfolio wireframe specs, card systems, and responsive breakpoint sheets.",
        detailed_description=f"{DEMO_DISCLAIMER}. Contains design token specifications, component state matrices, and wireframe layouts for creative portfolios.",
        tags=["ui-kit", "portfolio", "wireframes", "demo"],
        includes=["README.md", "ui-tokens.json", "wireframe-grid.svg"],
    ),
    DemoProductSpec(
        slug="demo-creative-icon-collection",
        name="Creative Icon Collection",
        category_slug="design-and-graphics",
        seller_slug="demo-pixelcraft-studio",
        original_price=Decimal("149.00"),
        sale_price=None,
        product_type="Icon Pack",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="A collection of clean geometric vector icons organized for apps and dashboards.",
        main_description="24px-grid aligned monochrome vector icons packaged with usage instructions and metadata index.",
        detailed_description=f"{DEMO_DISCLAIMER}. Packaged ZIP containing original vector glyph definitions, icon manifest JSON, and sizing guide.",
        tags=["icons", "vector", "ui-assets", "demo"],
        includes=["README.md", "icons-manifest.json", "12-vector-icons.svg"],
    ),
    DemoProductSpec(
        slug="demo-brand-identity-starter-pack",
        name="Brand Identity Starter Pack",
        category_slug="design-and-graphics",
        seller_slug=None,
        original_price=Decimal("399.00"),
        sale_price=None,
        product_type="Brand Guidelines",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="Logo presentation workbook and visual brand guideline starter document.",
        main_description="Complete starter guide covering typography pairings, palette ratios, and clearspace rules.",
        detailed_description=f"{DEMO_DISCLAIMER}. Multi-page PDF brand identity handbook built for rapid client onboarding and creative studio pitches.",
        tags=["branding", "guidelines", "pdf", "demo"],
        includes=["10-section PDF brand manual", "color ratio worksheets", "typography hierarchy chart"],
    ),
    # 2. Documents & Productivity
    DemoProductSpec(
        slug="demo-ultimate-notion-productivity-dashboard",
        name="Ultimate Notion Productivity Dashboard",
        category_slug="documents-and-productivity",
        seller_slug="demo-bizflow-collective",
        original_price=Decimal("249.00"),
        sale_price=Decimal("179.00"),
        product_type="Productivity Template",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Task, goal, and habit tracking template bundle with importable CSV/Markdown databases.",
        main_description="All-in-one personal execution workspace with sprint boards, daily checklists, and habit scorecards.",
        detailed_description=f"{DEMO_DISCLAIMER}. Includes structured Markdown page templates, CSV database starters, and setup README.",
        tags=["notion", "productivity", "habits", "demo"],
        includes=["README.md", "tasks-template.csv", "dashboard-blueprint.md"],
    ),
    DemoProductSpec(
        slug="demo-professional-resume-bundle",
        name="Professional Resume Bundle",
        category_slug="documents-and-productivity",
        seller_slug="demo-bizflow-collective",
        original_price=Decimal("199.00"),
        sale_price=None,
        product_type="Document Bundle",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="Clean ATS-friendly resume structures and executive cover letter formatting guides.",
        main_description="Structured single-column and two-column resume frameworks paired with matching cover letter templates.",
        detailed_description=f"{DEMO_DISCLAIMER}. Printable multi-page PDF reference layouts and impact-bullet writing prompts.",
        tags=["resume", "career", "cover-letter", "demo"],
        includes=["Resume layout specs (PDF)", "Cover letter frameworks", "Action verb reference"],
    ),
    DemoProductSpec(
        slug="demo-personal-finance-tracker",
        name="Personal Finance Tracker",
        category_slug="documents-and-productivity",
        seller_slug="demo-bizflow-collective",
        original_price=Decimal("129.00"),
        sale_price=None,
        product_type="Spreadsheet Template",
        asset_ext=".csv",
        asset_mime="text/csv",
        short_description="Structured CSV ledger for monthly budgeting, savings targets, and expense categorization.",
        main_description="Import-ready budget spreadsheet with realistic sample categories, INR totals, and monthly variance columns.",
        detailed_description=f"{DEMO_DISCLAIMER}. Clean RFC-4180 CSV spreadsheet compatible with Excel, Google Sheets, and LibreOffice Calc.",
        tags=["finance", "budget", "csv", "demo"],
        includes=["Monthly budget ledger CSV", "Sample expense categories", "Savings allocation columns"],
    ),
    DemoProductSpec(
        slug="demo-weekly-planner-collection",
        name="Weekly Planner Collection",
        category_slug="documents-and-productivity",
        seller_slug=None,
        original_price=Decimal("99.00"),
        sale_price=None,
        product_type="Printable Planner",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="Printable weekly focus blocks, monthly milestones, and retrospective review pages.",
        main_description="Minimalist A4/Letter planner sheets designed for calm weekly time-blocking and priority reviews.",
        detailed_description=f"{DEMO_DISCLAIMER}. Multi-page printable PDF collection prepared for digital annotation or print binding.",
        tags=["planner", "weekly", "printable", "demo"],
        includes=["Weekly time-block sheet (PDF)", "Monthly overview grid", "End-of-week review log"],
    ),
    # 3. Education & Learning
    DemoProductSpec(
        slug="demo-python-programming-starter-guide",
        name="Python Programming Starter Guide",
        category_slug="education-and-learning",
        seller_slug="demo-learnvault-academy",
        original_price=Decimal("199.00"),
        sale_price=Decimal("149.00"),
        product_type="Study Guide PDF",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="Beginner-friendly Python syntax, control flow, functions, and file handling PDF guide.",
        main_description="Step-by-step introductory Python workbook featuring clear examples and beginner practice exercises.",
        detailed_description=f"{DEMO_DISCLAIMER}. Covers variables, collections, list comprehensions, virtual environments, and standard library basics.",
        tags=["python", "programming", "ebook", "demo"],
        includes=["Python core chapters (PDF)", "Practice exercises", "Quick syntax cheat sheet"],
    ),
    DemoProductSpec(
        slug="demo-data-structures-algorithms-notes",
        name="Data Structures & Algorithms Notes",
        category_slug="education-and-learning",
        seller_slug="demo-learnvault-academy",
        original_price=Decimal("299.00"),
        sale_price=None,
        product_type="Study Notes PDF",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="Structured DSA revision notes covering arrays, trees, graphs, sorting, and Big-O complexity.",
        main_description="Concise exam and interview revision handbook summarizing core algorithmic patterns and complexity tables.",
        detailed_description=f"{DEMO_DISCLAIMER}. High-signal study PDF organized by topic with recurrence patterns and traversal comparisons.",
        tags=["dsa", "algorithms", "interview-prep", "demo"],
        includes=["Time/space complexity matrix", "Tree & graph patterns", "Dynamic programming primer"],
    ),
    DemoProductSpec(
        slug="demo-computer-networks-study-handbook",
        name="Computer Networks Study Handbook",
        category_slug="education-and-learning",
        seller_slug="demo-learnvault-academy",
        original_price=Decimal("249.00"),
        sale_price=None,
        product_type="Handbook PDF",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="Networking fundamentals handbook spanning OSI layers, TCP/UDP, DNS, TLS, and HTTP.",
        main_description="Practical protocol reference explaining packet flow, subnetting basics, and modern web transport security.",
        detailed_description=f"{DEMO_DISCLAIMER}. Comprehensive revision PDF tailored for university coursework and systems interviews.",
        tags=["networking", "tcp-ip", "http", "demo"],
        includes=["OSI vs TCP/IP summary", "DNS & TLS handshake notes", "Port & protocol reference"],
    ),
    DemoProductSpec(
        slug="demo-mathematics-formula-reference",
        name="Mathematics Formula Reference",
        category_slug="education-and-learning",
        seller_slug=None,
        original_price=Decimal("129.00"),
        sale_price=None,
        product_type="Reference PDF",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="Structured algebra, calculus, probability, and linear algebra formula reference sheet.",
        main_description="Compact desk reference uniting key identities, derivatives, distributions, and matrix operations.",
        detailed_description=f"{DEMO_DISCLAIMER}. Indexed formula PDF built for fast quantitative review across STEM modules.",
        tags=["mathematics", "formulas", "calculus", "demo"],
        includes=["Linear algebra identities", "Calculus derivatives & integrals", "Probability rules"],
    ),
    # 4. Development & Technology
    DemoProductSpec(
        slug="demo-modern-portfolio-website-template",
        name="Modern Portfolio Website Template",
        category_slug="development-and-technology",
        seller_slug="demo-codeforge-labs",
        original_price=Decimal("349.00"),
        sale_price=Decimal("249.00"),
        product_type="Website Template",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Responsive HTML/CSS/JavaScript developer portfolio template packaged inside a clean ZIP.",
        main_description="Zero-dependency static site starter with accessible layout sections, responsive grid, and theme variables.",
        detailed_description=f"{DEMO_DISCLAIMER}. Packaged securely as a ZIP archive containing README.md, index.html, styles.css, and app.js.",
        tags=["html", "css", "portfolio", "template", "demo"],
        includes=["README.md", "index.html", "styles.css", "app.js"],
    ),
    DemoProductSpec(
        slug="demo-react-component-starter-kit",
        name="React Component Starter Kit",
        category_slug="development-and-technology",
        seller_slug="demo-codeforge-labs",
        original_price=Decimal("599.00"),
        sale_price=None,
        product_type="React Kit",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Reusable accessible React UI primitives, hooks, and theme tokens in a ZIP starter kit.",
        main_description="Modular frontend component pack including buttons, data cards, modal dialog hooks, and responsive nav.",
        detailed_description=f"{DEMO_DISCLAIMER}. Contains JSX component modules, CSS token styles, package manifest, and README.md.",
        tags=["react", "components", "frontend", "demo"],
        includes=["README.md", "package.json", "src/Button.jsx", "src/Card.jsx"],
    ),
    DemoProductSpec(
        slug="demo-python-automation-toolkit",
        name="Python Automation Toolkit",
        category_slug="development-and-technology",
        seller_slug="demo-codeforge-labs",
        original_price=Decimal("449.00"),
        sale_price=None,
        product_type="Code Toolkit",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Example standard-library Python CLI scripts for CSV cleanup, file indexing, and batch renames.",
        main_description="Lightweight automation scripts demonstrating clean CLI argument parsing and idempotent folder hygiene.",
        detailed_description=f"{DEMO_DISCLAIMER}. Secure ZIP package containing pure-Python helper modules, sample data, and README.md.",
        tags=["python", "automation", "cli", "demo"],
        includes=["README.md", "csv_normalizer.py", "folder_digest.py"],
    ),
    DemoProductSpec(
        slug="demo-rest-api-starter-project",
        name="REST API Starter Project",
        category_slug="development-and-technology",
        seller_slug=None,
        original_price=Decimal("699.00"),
        sale_price=None,
        product_type="Backend Starter",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="A documented demonstration FastAPI-style REST API project scaffold and OpenAPI blueprint.",
        main_description="Clean modular API architecture sample covering health endpoints, Pydantic schemas, and test structure.",
        detailed_description=f"{DEMO_DISCLAIMER}. Contains structured Python starter modules, schema examples, configuration template, and README.md.",
        tags=["fastapi", "rest-api", "backend", "demo"],
        includes=["README.md", "app/main.py", "app/schemas.py", "tests/test_health.py"],
    ),
    # 5. AI Resources & Automation
    DemoProductSpec(
        slug="demo-ai-productivity-prompt-library",
        name="AI Productivity Prompt Library",
        category_slug="ai-resources-and-automation",
        seller_slug="demo-codeforge-labs",
        original_price=Decimal("249.00"),
        sale_price=Decimal("169.00"),
        product_type="Prompt Library",
        asset_ext=".json",
        asset_mime="application/json",
        short_description="Categorized structured JSON library of system & task prompts for engineering, planning, and writing.",
        main_description="Machine-readable prompt collection featuring role frames, constraints, and evaluation checklists.",
        detailed_description=f"{DEMO_DISCLAIMER}. Validated UTF-8 JSON prompt catalog ready for tooling pipelines or prompt notebooks.",
        tags=["ai", "prompts", "json", "productivity", "demo"],
        includes=["20 structured prompt objects (JSON)", "Category taxonomy", "Evaluation rubric fields"],
    ),
    DemoProductSpec(
        slug="demo-ai-content-creation-toolkit",
        name="AI Content Creation Toolkit",
        category_slug="ai-resources-and-automation",
        seller_slug="demo-pixelcraft-studio",
        original_price=Decimal("349.00"),
        sale_price=None,
        product_type="AI Toolkit",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Example editorial workflows, outline prompts, and content repurposing templates in a ZIP pack.",
        main_description="End-to-end content pipeline connecting long-form briefs to social threads and newsletter summaries.",
        detailed_description=f"{DEMO_DISCLAIMER}. Includes Markdown editorial playbooks, JSON prompt chains, and README.md.",
        tags=["ai-writing", "content", "workflow", "demo"],
        includes=["README.md", "editorial-playbook.md", "repurpose-chain.json"],
    ),
    DemoProductSpec(
        slug="demo-research-assistant-prompt-pack",
        name="Research Assistant Prompt Pack",
        category_slug="ai-resources-and-automation",
        seller_slug="demo-learnvault-academy",
        original_price=Decimal("199.00"),
        sale_price=None,
        product_type="Markdown Pack",
        asset_ext=".md",
        asset_mime="text/markdown",
        short_description="Structured Markdown prompts for literature synthesis, claim verification, and study outlines.",
        main_description="Academic and technical research prompt handbook emphasizing source grounding and concise synthesis.",
        detailed_description=f"{DEMO_DISCLAIMER}. Clean Markdown prompt guide compatible with Obsidian, Notion, and code editors.",
        tags=["research", "prompts", "markdown", "demo"],
        includes=["Synthesis & summary prompts (MD)", "Source comparison checklist", "Study outline template"],
    ),
    DemoProductSpec(
        slug="demo-automation-workflow-blueprint",
        name="Automation Workflow Blueprint",
        category_slug="ai-resources-and-automation",
        seller_slug=None,
        original_price=Decimal("399.00"),
        sale_price=None,
        product_type="Workflow Blueprint",
        asset_ext=".json",
        asset_mime="application/json",
        short_description="Declarative JSON automation workflow definitions covering webhook triage and digest routing.",
        main_description="Reference node-graph schemas for event classification, retry backoff, and human-in-the-loop escalation.",
        detailed_description=f"{DEMO_DISCLAIMER}. Standards-friendly JSON workflow blueprints designed for automation architecture study.",
        tags=["automation", "workflow", "webhooks", "json", "demo"],
        includes=["3 reference workflow graphs (JSON)", "Retry & backoff policy schema", "Webhook payload contract"],
    ),
    # 6. Digital Marketing
    DemoProductSpec(
        slug="demo-instagram-content-calendar",
        name="Instagram Content Calendar",
        category_slug="digital-marketing",
        seller_slug="demo-pixelcraft-studio",
        original_price=Decimal("199.00"),
        sale_price=None,
        product_type="Marketing CSV",
        asset_ext=".csv",
        asset_mime="text/csv",
        short_description="30-day editable planning spreadsheet covering reels, carousels, hooks, and CTA cadence.",
        main_description="Ready-to-import 30-day social publishing schedule balancing educational, product, and proof posts.",
        detailed_description=f"{DEMO_DISCLAIMER}. RFC-4180 CSV calendar importable into spreadsheets, Notion, and Airtable.",
        tags=["instagram", "content-calendar", "csv", "demo"],
        includes=["30-day post schedule CSV", "Format & pillar tags", "CTA tracking columns"],
    ),
    DemoProductSpec(
        slug="demo-digital-marketing-strategy-workbook",
        name="Digital Marketing Strategy Workbook",
        category_slug="digital-marketing",
        seller_slug="demo-learnvault-academy",
        original_price=Decimal("299.00"),
        sale_price=Decimal("219.00"),
        product_type="Workbook PDF",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="Campaign positioning, funnel metrics, ICP mapping, and launch retrospective PDF workbook.",
        main_description="Guided campaign workbook helping small teams align audience messaging, channels, and conversion targets.",
        detailed_description=f"{DEMO_DISCLAIMER}. Structured multi-page PDF strategy playbook with campaign brief worksheets.",
        tags=["marketing", "strategy", "workbook", "demo"],
        includes=["ICP & positioning canvas (PDF)", "Channel budget split worksheet", "Launch checklist"],
    ),
    DemoProductSpec(
        slug="demo-social-media-analytics-dashboard",
        name="Social Media Analytics Dashboard",
        category_slug="digital-marketing",
        seller_slug="demo-codeforge-labs",
        original_price=Decimal("249.00"),
        sale_price=None,
        product_type="Analytics Pack",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Sample spreadsheet CSV datasets and KPI formula documentation for cross-channel social reporting.",
        main_description="Monthly engagement, reach, CTR, and conversion funnel datasets packaged cleanly with metric definitions.",
        detailed_description=f"{DEMO_DISCLAIMER}. ZIP archive containing channel analytics CSVs, KPI dictionary Markdown, and README.md.",
        tags=["analytics", "social-media", "kpi", "demo"],
        includes=["README.md", "monthly-channel-metrics.csv", "kpi-formulas.md"],
    ),
    DemoProductSpec(
        slug="demo-small-business-marketing-kit",
        name="Small Business Marketing Kit",
        category_slug="digital-marketing",
        seller_slug=None,
        original_price=Decimal("349.00"),
        sale_price=None,
        product_type="Marketing Kit",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Launch checklists, email newsletter outlines, and seasonal campaign calendar templates.",
        main_description="Practical small-business growth starter combining launch timelines, copy templates, and checklist sheets.",
        detailed_description=f"{DEMO_DISCLAIMER}. Complete ZIP kit with README.md, campaign checklist Markdown, and promo calendar CSV.",
        tags=["small-business", "marketing", "launch", "demo"],
        includes=["README.md", "launch-checklist.md", "promo-calendar.csv"],
    ),
    # 7. Audio & Video
    DemoProductSpec(
        slug="demo-cinematic-video-editing-presets",
        name="Cinematic Video Editing Presets",
        category_slug="audio-and-video",
        seller_slug="demo-pixelcraft-studio",
        original_price=Decimal("399.00"),
        sale_price=None,
        product_type="Editing Presets",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Example color-grading LUT parameter files (.cube specs) and timeline transition guide.",
        main_description="Warm filmic, clean documentary, and crisp product-showcase grading preset definitions in a ZIP bundle.",
        detailed_description=f"{DEMO_DISCLAIMER}. Includes 3D LUT `.cube` parameter files, color curve notes, and README.md.",
        tags=["video-editing", "luts", "color-grading", "demo"],
        includes=["README.md", "warm-amber.cube", "clean-studio.cube"],
    ),
    DemoProductSpec(
        slug="demo-royalty-free-sound-effects-pack",
        name="Royalty-Free Sound Effects Demo Pack",
        category_slug="audio-and-video",
        seller_slug="demo-learnvault-academy",
        original_price=Decimal("249.00"),
        sale_price=Decimal("179.00"),
        product_type="Audio WAV",
        asset_ext=".wav",
        asset_mime="audio/wav",
        short_description="Original synthesized 16-bit PCM WAV UI chime & transition tone for video and app previews.",
        main_description="Clean studio-synthesized WAV sound cue suitable for product demos, notifications, and transitions.",
        detailed_description=f"{DEMO_DISCLAIMER}. Valid uncompressed 44.1kHz 16-bit mono RIFF/WAVE audio file synthesized deterministically.",
        tags=["sound-effects", "wav", "audio", "demo"],
        includes=["44.1kHz 16-bit PCM WAV audio", "Original harmonic chime sequence"],
    ),
    DemoProductSpec(
        slug="demo-motion-graphics-starter-pack",
        name="Motion Graphics Starter Pack",
        category_slug="audio-and-video",
        seller_slug="demo-codeforge-labs",
        original_price=Decimal("499.00"),
        sale_price=None,
        product_type="Motion Assets",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Demonstration motion keyframe specs, lower-third timings, and easing presets in a ZIP archive.",
        main_description="Structured JSON keyframe animations and timing curves for title reveals, badges, and callouts.",
        detailed_description=f"{DEMO_DISCLAIMER}. Contains motion timing JSON definitions, storyboard specs, and README.md.",
        tags=["motion-graphics", "animation", "easing", "demo"],
        includes=["README.md", "title-reveal-keyframes.json", "easing-curves.json"],
    ),
    DemoProductSpec(
        slug="demo-video-creator-resource-bundle",
        name="Video Creator Resource Bundle",
        category_slug="audio-and-video",
        seller_slug=None,
        original_price=Decimal("299.00"),
        sale_price=None,
        product_type="Creator Bundle",
        asset_ext=".zip",
        asset_mime="application/zip",
        short_description="Sample YouTube production checklist, audio notification WAV stinger, and pacing sheet.",
        main_description="Starter production pack uniting pre-shoot scripts, audio transition stingers, and B-roll checklists.",
        detailed_description=f"{DEMO_DISCLAIMER}. Includes synthesized WAV audio stinger, pre-flight checklist Markdown, and README.md.",
        tags=["video-creator", "production", "wav", "demo"],
        includes=["README.md", "intro-stinger.wav", "production-checklist.md"],
    ),
    # 8. Business Resources
    DemoProductSpec(
        slug="demo-startup-pitch-deck-template",
        name="Startup Pitch Deck Template",
        category_slug="business-resources",
        seller_slug="demo-bizflow-collective",
        original_price=Decimal("399.00"),
        sale_price=Decimal("299.00"),
        product_type="Presentation PDF",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="12-slide investor pitch framework covering problem, market sizing, traction, and unit economics.",
        main_description="Concise seed-stage presentation blueprint structured around clarity, narrative pacing, and clean metrics.",
        detailed_description=f"{DEMO_DISCLAIMER}. Printable multi-page PDF slide structure with speaker prompt annotations.",
        tags=["pitch-deck", "startup", "fundraising", "demo"],
        includes=["12-slide outline (PDF)", "Metrics framing prompts", "Appendix checklist"],
    ),
    DemoProductSpec(
        slug="demo-business-plan-workbook",
        name="Business Plan Workbook",
        category_slug="business-resources",
        seller_slug="demo-bizflow-collective",
        original_price=Decimal("299.00"),
        sale_price=None,
        product_type="Workbook PDF",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="Structured business planning PDF spanning value proposition, pricing tiers, and 90-day milestones.",
        main_description="Practical founder workbook translating strategy concepts into measurable quarterly operating goals.",
        detailed_description=f"{DEMO_DISCLAIMER}. Multi-page business planning PDF for digital creators and SaaS founders.",
        tags=["business-plan", "operations", "pdf", "demo"],
        includes=["Lean canvas summary (PDF)", "Go-to-market milestones", "Risk register template"],
    ),
    DemoProductSpec(
        slug="demo-startup-financial-model",
        name="Startup Financial Model",
        category_slug="business-resources",
        seller_slug="demo-bizflow-collective",
        original_price=Decimal("449.00"),
        sale_price=None,
        product_type="Financial CSV",
        asset_ext=".csv",
        asset_mime="text/csv",
        short_description="12-month sample SaaS & digital product revenue, COGS, burn, and runway CSV projection model.",
        main_description="Structured financial projection CSV formatted in INR for easy import into Excel or Google Sheets.",
        detailed_description=f"{DEMO_DISCLAIMER}. Demonstration monthly P&L forecast CSV containing synthetic sample figures only.",
        tags=["financial-model", "forecast", "csv", "demo"],
        includes=["12-month P&L CSV", "MRR & CAC sample assumptions", "Runway summary rows"],
    ),
    DemoProductSpec(
        slug="demo-business-proposal-template",
        name="Business Proposal Template",
        category_slug="business-resources",
        seller_slug=None,
        original_price=Decimal("199.00"),
        sale_price=None,
        product_type="Proposal PDF",
        asset_ext=".pdf",
        asset_mime="application/pdf",
        short_description="Professional client scope-of-work, milestone payment terms, and project proposal PDF template.",
        main_description="Client-ready agency and consulting proposal structure covering deliverables, timelines, and sign-off.",
        detailed_description=f"{DEMO_DISCLAIMER}. Clean PDF proposal guide formatted for independent studios and consultants.",
        tags=["proposal", "consulting", "sow", "demo"],
        includes=["Executive summary layout (PDF)", "Scope & timeline table", "Milestone acceptance clause sample"],
    ),
)


# ---------------------------------------------------------------------------
# Database Safety Verification
# ---------------------------------------------------------------------------


def verify_seed_target(db: Session, *, allow_test_db: bool = False) -> str:
    """Verify environment, host, and active PostgreSQL database before any DB write."""
    env_name = (settings.ENVIRONMENT or "").strip().lower()
    allowed_envs = TEST_ALLOWED_ENVS if allow_test_db else LOCAL_ALLOWED_ENVS
    if env_name not in allowed_envs:
        raise RuntimeError(
            f"Refusing demo seed: ENVIRONMENT='{settings.ENVIRONMENT}' is not permitted."
        )

    bind = db.get_bind()
    engine = getattr(bind, "engine", bind)
    url_obj = make_url(str(engine.url))
    host = (url_obj.host or "").strip().lower()
    if host not in ALLOWED_LOCAL_HOSTS:
        raise RuntimeError(
            f"Refusing demo seed: database host '{host or 'unknown'}' must be localhost or 127.0.0.1."
        )

    active_db = (db.scalar(text("SELECT current_database()")) or "").strip()
    if not active_db or active_db == "digiverse" or "prod" in active_db.lower() or "staging" in active_db.lower():
        raise RuntimeError(
            f"Refusing demo seed: active database '{active_db}' is protected and forbidden."
        )

    allowed_dbs = {"digiverse_local", "digiverse_test"} if allow_test_db else {"digiverse_local"}
    if active_db not in allowed_dbs:
        raise RuntimeError(
            f"Refusing demo seed: active database '{active_db}' is not in allowed targets {sorted(allowed_dbs)}."
        )

    return active_db


# ---------------------------------------------------------------------------
# Pure-Python Binary File Generators (No External Dependencies)
# ---------------------------------------------------------------------------


def _escape_pdf_text(value: str) -> str:
    normalized = value.replace("\u2014", "-").replace("\u2013", "-")
    ascii_safe = normalized.encode("ascii", errors="replace").decode("ascii")
    return ascii_safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_demo_pdf(title: str, subtitle: str, sections: list[tuple[str, list[str]]]) -> bytes:
    """Generate a valid multi-section %PDF-1.4 document using standard Helvetica fonts."""
    stream_lines = [
        "BT",
        "/F2 18 Tf",
        "54 756 Td",
        f"({_escape_pdf_text(title)}) Tj",
        "/F1 10 Tf",
        "0 -20 Td",
        f"({_escape_pdf_text(DEMO_DISCLAIMER)}) Tj",
        "0 -16 Td",
        f"({_escape_pdf_text(subtitle)}) Tj",
        "0 -24 Td",
    ]
    for heading, bullets in sections:
        stream_lines.extend(
            [
                "/F2 12 Tf",
                f"({_escape_pdf_text(heading)}) Tj",
                "/F1 10 Tf",
                "0 -16 Td",
            ]
        )
        for line in bullets:
            stream_lines.extend([f"({_escape_pdf_text('- ' + line)}) Tj", "0 -14 Td"])
        stream_lines.append("0 -10 Td")
    stream_lines.append("ET")
    content_bytes = "\n".join(stream_lines).encode("ascii")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>\n"
            b"endobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n",
        (
            f"6 0 obj\n<< /Length {len(content_bytes)} >>\nstream\n".encode("ascii")
            + content_bytes
            + b"\nendstream\nendobj\n"
        ),
    ]

    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = [0]
    for obj in objects:
        offsets.append(len(buf))
        buf.extend(obj)

    xref_pos = len(buf)
    buf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    buf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        buf.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    buf.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(buf)


def build_demo_wav(seed_index: int, duration_seconds: float = 1.2) -> bytes:
    """Generate a clean 44.1kHz 16-bit PCM WAV chime sequence via stdlib wave."""
    sample_rate = 44100
    total_frames = int(sample_rate * duration_seconds)
    base_freq = 440.0 + (seed_index % 7) * 55.0
    frames = bytearray()
    for i in range(total_frames):
        t = i / sample_rate
        envelope = math.exp(-3.2 * t)
        note_freq = base_freq if t < 0.45 else base_freq * 1.25
        val = 0.35 * envelope * (
            0.7 * math.sin(2.0 * math.pi * note_freq * t)
            + 0.3 * math.sin(4.0 * math.pi * note_freq * t)
        )
        sample = max(-32767, min(32767, int(val * 32767)))
        frames.extend(struct.pack("<h", sample))

    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))
    return bio.getvalue()


def _zip_from_entries(entries: dict[str, bytes]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, payload in entries.items():
            info = zipfile.ZipInfo(path, date_time=(2026, 11, 22, 12, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, payload)
    return bio.getvalue()


def build_demo_asset_bytes(spec: DemoProductSpec, index: int) -> tuple[str, bytes, str]:
    """Generate authentic binary content matching each product's declared format."""
    readme_text = (
        f"# {spec.name}\n\n"
        f"**{DEMO_DISCLAIMER}**\n\n"
        f"- Category: {spec.category_slug}\n"
        f"- Product Type: {spec.product_type}\n"
        f"- Included items: {', '.join(spec.includes)}\n\n"
        "This archive contains original synthetic sample resources generated exclusively\n"
        "to test DIGI-VERSE discovery, checkout, and authenticated download streaming.\n"
    ).encode("utf-8")

    if spec.asset_ext == ".pdf":
        sections = [
            ("Overview", [spec.short_description, spec.main_description]),
            ("Included Modules", spec.includes),
            (
                "Sample Exercise & Usage",
                [
                    "Step 1: Review checklist milestones in order.",
                    "Step 2: Duplicate baseline metrics into your working copy.",
                    "Step 3: Validate outputs against the target specification.",
                ],
            ),
        ]
        return (
            f"{spec.slug}.pdf",
            build_demo_pdf(spec.name, f"Category: {spec.category_slug} | {spec.product_type}", sections),
            spec.asset_mime,
        )

    if spec.asset_ext == ".csv":
        if "finance" in spec.slug:
            csv_body = (
                f"# {DEMO_DISCLAIMER} — {spec.name}\n"
                "Month,Category,Planned_INR,Actual_INR,Variance_INR,Notes\n"
                "2026-11,Housing & Utilities,18000.00,17650.00,350.00,Sample budget row\n"
                "2026-11,Groceries,8500.00,8120.00,380.00,Sample budget row\n"
                "2026-11,Digital Subscriptions,1499.00,1499.00,0.00,Sample budget row\n"
                "2026-11,Emergency Savings,10000.00,10000.00,0.00,Target met\n"
            )
        elif "financial-model" in spec.slug:
            csv_body = (
                f"# {DEMO_DISCLAIMER} — {spec.name}\n"
                "Month,New_Customers,Active_Subscribers,MRR_INR,COGS_INR,Operating_Expenses_INR,Net_Cashflow_INR\n"
                "Month-01,25,25,12500.00,1800.00,22000.00,-11300.00\n"
                "Month-02,40,62,31000.00,3400.00,23500.00,4100.00\n"
                "Month-03,55,110,55000.00,5200.00,25000.00,24800.00\n"
                "Month-04,70,172,86000.00,7400.00,28000.00,50600.00\n"
            )
        else:
            csv_body = (
                f"# {DEMO_DISCLAIMER} — {spec.name}\n"
                "Day,Channel,Content_Format,Topic_Pillar,Hook_Sample,Call_To_Action\n"
                "Day-01,Instagram,Carousel,Education,3 UI spacing rules that fix hierarchy,Save checklist\n"
                "Day-02,Instagram,Reel,Behind-the-Scenes,How we organize design tokens in 5 mins,Comment TOKENS\n"
                "Day-03,Instagram,Single Post,Social Proof,Sample creator workflow case study,Visit bio store\n"
                "Day-04,Instagram,Carousel,Tips,Typography pairing starter combinations,Share with team\n"
            )
        return f"{spec.slug}.csv", csv_body.encode("utf-8"), spec.asset_mime

    if spec.asset_ext == ".json":
        payload = {
            "notice": DEMO_DISCLAIMER,
            "product": spec.name,
            "slug": spec.slug,
            "version": "1.0.0-demo",
            "category": spec.category_slug,
            "items": [
                {
                    "id": f"demo-entry-{i}",
                    "title": f"Sample Entry {i} for {spec.name}",
                    "description": f"Synthetic structured definition #{i} for preview testing.",
                    "tags": spec.tags,
                }
                for i in range(1, 5)
            ],
        }
        return (
            f"{spec.slug}.json",
            json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
            spec.asset_mime,
        )

    if spec.asset_ext == ".md":
        md = (
            f"# {spec.name}\n\n"
            f"> **{DEMO_DISCLAIMER}**\n\n"
            f"{spec.short_description}\n\n"
            "## Prompt Workflow 1 — Literature Synthesis\n"
            "- Objective: Summarize key claims and assumptions cleanly.\n"
            "- Constraints: Cite only verified excerpts.\n\n"
            "## Prompt Workflow 2 — Critical Comparison Matrix\n"
            "- Output columns: Method | Strengths | Limitations | Evidence\n"
        )
        return f"{spec.slug}.md", md.encode("utf-8"), spec.asset_mime

    if spec.asset_ext == ".wav":
        return f"{spec.slug}.wav", build_demo_wav(index), spec.asset_mime

    # Structured .zip bundles (web templates, icon packs, toolkits, LUTs, creator packs)
    entries: dict[str, bytes] = {"README.md": readme_text}
    if "portfolio-website" in spec.slug:
        entries["index.html"] = (
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<title>{spec.name} ({DEMO_DISCLAIMER})</title>"
            "<link rel='stylesheet' href='styles.css'></head>"
            f"<body><main><h1>{spec.name}</h1><p>{DEMO_DISCLAIMER}</p></main>"
            "<script src='app.js'></script></body></html>\n"
        ).encode("utf-8")
        entries["styles.css"] = b"body { font-family: system-ui, sans-serif; margin: 2rem; color: #1f2937; }\n"
        entries["app.js"] = b"console.info('DIGI-VERSE DEMO SAMPLE - FOR PREVIEW AND TESTING ONLY');\n"
    elif "react-component" in spec.slug:
        entries["package.json"] = json.dumps({"name": spec.slug, "version": "1.0.0-demo", "private": True}, indent=2).encode("utf-8")
        entries["src/Button.jsx"] = b"export const DemoButton = ({ children }) => <button type='button'>{children}</button>;\n"
        entries["src/Card.jsx"] = b"export const DemoCard = ({ title, body }) => <article><h3>{title}</h3><p>{body}</p></article>;\n"
    elif "python-automation" in spec.slug:
        entries["csv_normalizer.py"] = (
            f'"""{DEMO_DISCLAIMER}"""\nimport csv\n\ndef normalize_headers(rows):\n    return rows\n'
        ).encode("utf-8")
        entries["folder_digest.py"] = b"import hashlib\n# Synthetic automation example\n"
    elif "rest-api" in spec.slug:
        entries["app/main.py"] = (
            f'"""{DEMO_DISCLAIMER}"""\n'
            "from fastapi import FastAPI\napp = FastAPI(title='Demo API Starter')\n"
            "@app.get('/health')\ndef health(): return {'status': 'ok'}\n"
        ).encode("utf-8")
        entries["tests/test_health.py"] = b"def test_placeholder():\n    assert True\n"
    elif "video-editing-presets" in spec.slug:
        entries["warm-amber.cube"] = (
            f"# {DEMO_DISCLAIMER}\nTITLE \"Demo Warm Amber\"\nLUT_3D_SIZE 2\n"
            "0.0 0.0 0.0\n1.0 0.0 0.0\n0.0 1.0 0.0\n1.0 1.0 0.0\n"
            "0.0 0.0 1.0\n1.0 0.0 1.0\n0.0 1.0 1.0\n1.0 1.0 1.0\n"
        ).encode("utf-8")
        entries["clean-studio.cube"] = b"# Synthetic clean studio preset\nLUT_3D_SIZE 2\n"
    elif "video-creator-resource-bundle" in spec.slug:
        entries["intro-stinger.wav"] = build_demo_wav(index + 3, duration_seconds=0.8)
        entries["production-checklist.md"] = f"# Pre-Shoot Checklist\n\n{DEMO_DISCLAIMER}\n- Audio check\n- Lighting check\n".encode("utf-8")
    elif "creative-icon" in spec.slug:
        entries["icons-manifest.json"] = json.dumps({"notice": DEMO_DISCLAIMER, "grid": "24x24", "count": 12}, indent=2).encode("utf-8")
        entries["icons/grid-preview.svg"] = (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor'>"
            "<rect x='3' y='3' width='18' height='18' rx='3'/></svg>\n"
        ).encode("utf-8")
    else:
        entries["manifest.json"] = json.dumps(
            {"notice": DEMO_DISCLAIMER, "product": spec.name, "includes": spec.includes}, indent=2
        ).encode("utf-8")
        entries["sample-data.csv"] = f"# {DEMO_DISCLAIMER}\nItem,Status,Category\n{spec.name},Demo,Seed\n".encode("utf-8")

    return f"{spec.slug}.zip", _zip_from_entries(entries), spec.asset_mime


# ---------------------------------------------------------------------------
# Pure-Python 640x400 Clean Vector-Style Cover Generator (Zero Pixel Text)
# ---------------------------------------------------------------------------


def _lerp_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    clamped = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * clamped),
        int(c1[1] + (c2[1] - c1[1]) * clamped),
        int(c1[2] + (c2[2] - c1[2]) * clamped),
    )


def _blend_pixel(buf: bytearray, idx: int, color: tuple[int, int, int], alpha: float) -> None:
    a = max(0.0, min(1.0, alpha))
    inv = 1.0 - a
    buf[idx] = int(buf[idx] * inv + color[0] * a)
    buf[idx + 1] = int(buf[idx + 1] * inv + color[1] * a)
    buf[idx + 2] = int(buf[idx + 2] * inv + color[2] * a)


def _fill_soft_gradient(
    width: int,
    height: int,
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
) -> bytearray:
    buf = bytearray(width * height * 3)
    stride = width * 3
    for y in range(height):
        row_c = _lerp_color(top_color, bottom_color, y / max(1, height - 1))
        row_bytes = bytes(row_c) * width
        buf[y * stride : (y + 1) * stride] = row_bytes
    return buf


def _draw_rect(buf: bytearray, width: int, height: int, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(width, x + w)
    y1 = min(height, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    row_bytes = bytes(color) * (x1 - x0)
    stride = width * 3
    for py in range(y0, y1):
        start = py * stride + x0 * 3
        buf[start : start + len(row_bytes)] = row_bytes


def _draw_rounded_rect_aa(
    buf: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    color: tuple[int, int, int],
    alpha: float = 1.0,
) -> None:
    r = max(0, min(radius, w // 2, h // 2))
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(width, x + w)
    y1 = min(height, y + h)
    if x0 >= x1 or y0 >= y1:
        return

    stride = width * 3
    # Solid center bands when opaque
    if alpha >= 0.999 and r > 0:
        _draw_rect(buf, width, height, x + r, y, w - 2 * r, h, color)
        _draw_rect(buf, width, height, x, y + r, r, h - 2 * r, color)
        _draw_rect(buf, width, height, x + w - r, y + r, r, h - 2 * r, color)
    elif alpha >= 0.999:
        _draw_rect(buf, width, height, x, y, w, h, color)
        return

    corners = (
        (x + r, y + r, x, x + r, y, y + r),
        (x + w - r - 1, y + r, x + w - r, x + w, y, y + r),
        (x + r, y + h - r - 1, x, x + r, y + h - r, y + h),
        (x + w - r - 1, y + h - r - 1, x + w - r, x + w, y + h - r, y + h),
    )

    if alpha < 0.999:
        for py in range(y0, y1):
            for px in range(x0, x1):
                in_corner = False
                cov = 1.0
                for cx, cy, bx0, bx1, by0, by1 in corners:
                    if bx0 <= px < bx1 and by0 <= py < by1:
                        in_corner = True
                        dist = math.hypot(px - cx, py - cy)
                        if dist > r + 0.7:
                            cov = 0.0
                        elif dist > r - 0.7:
                            cov = max(0.0, min(1.0, (r + 0.7 - dist) / 1.4))
                        break
                if cov > 0.0:
                    _blend_pixel(buf, py * stride + px * 3, color, alpha * cov)
        return

    for cx, cy, bx0, bx1, by0, by1 in corners:
        for py in range(max(0, by0), min(height, by1)):
            for px in range(max(0, bx0), min(width, bx1)):
                dist = math.hypot(px - cx, py - cy)
                if dist <= r - 0.7:
                    idx = py * stride + px * 3
                    buf[idx : idx + 3] = bytes(color)
                elif dist < r + 0.7:
                    cov = (r + 0.7 - dist) / 1.4
                    _blend_pixel(buf, py * stride + px * 3, color, cov)


def _draw_card_with_border(
    buf: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    fill: tuple[int, int, int] = (255, 255, 255),
    border: tuple[int, int, int] = (226, 232, 240),
    shadow_alpha: float = 0.06,
) -> None:
    _draw_rounded_rect_aa(buf, width, height, x + 2, y + 6, w, h, radius, (15, 23, 42), alpha=shadow_alpha)
    _draw_rounded_rect_aa(buf, width, height, x, y, w, h, radius, border, alpha=1.0)
    _draw_rounded_rect_aa(buf, width, height, x + 1, y + 1, w - 2, h - 2, max(0, radius - 1), fill, alpha=1.0)


def _draw_circle_aa(
    buf: bytearray,
    width: int,
    height: int,
    cx: float,
    cy: float,
    r: float,
    color: tuple[int, int, int],
    alpha: float = 1.0,
) -> None:
    x0 = max(0, int(cx - r - 2))
    x1 = min(width, int(cx + r + 3))
    y0 = max(0, int(cy - r - 2))
    y1 = min(height, int(cy + r + 3))
    stride = width * 3
    for py in range(y0, y1):
        dy = py - cy
        for px in range(x0, x1):
            dist = math.hypot(px - cx, dy)
            if dist <= r - 0.7:
                cov = 1.0
            elif dist < r + 0.7:
                cov = (r + 0.7 - dist) / 1.4
            else:
                continue
            _blend_pixel(buf, py * stride + px * 3, color, alpha * cov)


def _draw_ring_aa(
    buf: bytearray,
    width: int,
    height: int,
    cx: float,
    cy: float,
    r: float,
    thickness: float,
    color: tuple[int, int, int],
    alpha: float = 1.0,
) -> None:
    half = thickness / 2.0
    x0 = max(0, int(cx - r - half - 2))
    x1 = min(width, int(cx + r + half + 3))
    y0 = max(0, int(cy - r - half - 2))
    y1 = min(height, int(cy + r + half + 3))
    stride = width * 3
    for py in range(y0, y1):
        dy = py - cy
        for px in range(x0, x1):
            diff = abs(math.hypot(px - cx, dy) - r)
            if diff <= half - 0.7:
                cov = 1.0
            elif diff < half + 0.7:
                cov = (half + 0.7 - diff) / 1.4
            else:
                continue
            _blend_pixel(buf, py * stride + px * 3, color, alpha * cov)


def _draw_line_aa(
    buf: bytearray,
    width: int,
    height: int,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    thickness: float,
    color: tuple[int, int, int],
    alpha: float = 1.0,
) -> None:
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-6:
        return
    half = thickness / 2.0
    bx0 = max(0, int(min(x1, x2) - half - 2))
    bx1 = min(width, int(max(x1, x2) + half + 3))
    by0 = max(0, int(min(y1, y2) - half - 2))
    by1 = min(height, int(max(y1, y2) + half + 3))
    stride = width * 3
    for py in range(by0, by1):
        for px in range(bx0, bx1):
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
            dist = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
            if dist <= half - 0.7:
                cov = 1.0
            elif dist < half + 0.7:
                cov = (half + 0.7 - dist) / 1.4
            else:
                continue
            _blend_pixel(buf, py * stride + px * 3, color, alpha * cov)


def _draw_dot_grid(
    buf: bytearray,
    width: int,
    height: int,
    spacing: int,
    color: tuple[int, int, int],
    alpha: float = 0.14,
) -> None:
    stride = width * 3
    for py in range(24, height - 16, spacing):
        for px in range(24, width - 16, spacing):
            _blend_pixel(buf, py * stride + px * 3, color, alpha)
            if px + 1 < width:
                _blend_pixel(buf, py * stride + (px + 1) * 3, color, alpha * 0.5)


def _encode_png_rgb(width: int, height: int, rgb_bytes: bytearray) -> bytes:
    stride = width * 3
    raw_scanlines = bytearray((stride + 1) * height)
    for y in range(height):
        dst = y * (stride + 1)
        raw_scanlines[dst] = 0
        src = y * stride
        raw_scanlines[dst + 1 : dst + 1 + stride] = rgb_bytes[src : src + stride]

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        body = chunk_type + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw_scanlines), level=6)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def build_product_png(
    spec: DemoProductSpec,
    category: DemoCategorySpec,
    product_index: int,
    slide_index: int,
) -> bytes:
    """Render a clean, modern 640x400 SaaS marketplace artwork cover without pixel typography."""
    width, height = 640, 400
    bg_base, accent_base, ink = category.palette
    tint = _lerp_color(bg_base, (255, 255, 255), 0.35 + (slide_index * 0.12))
    bottom_tint = _lerp_color(bg_base, accent_base, 0.08 + ((product_index % 4) * 0.02))
    soft_accent = _lerp_color(accent_base, (255, 255, 255), 0.78)
    mid_accent = _lerp_color(accent_base, (255, 255, 255), 0.45)
    dark_slate = ink
    muted_line = (226, 232, 240)
    subtle_line = (241, 245, 249)

    buf = _fill_soft_gradient(width, height, tint, bottom_tint)
    _draw_dot_grid(buf, width, height, 28, accent_base, alpha=0.14)

    # Ambient soft decorative glow circles
    glow_x = 520 - (product_index % 3) * 36 - slide_index * 25
    glow_y = 90 + ((product_index + slide_index) % 3) * 45
    _draw_circle_aa(buf, width, height, glow_x, glow_y, 92, accent_base, alpha=0.07)
    _draw_circle_aa(buf, width, height, 110 + slide_index * 40, 320, 74, mid_accent, alpha=0.08)

    cat_slug = spec.category_slug
    var = product_index % 4

    if cat_slug == "design-and-graphics":
        # Artboards + swatch palettes + vector Bezier curve motif
        offset_x = var * 8 + slide_index * 10
        _draw_card_with_border(buf, width, height, 72 + offset_x, 56, 320, 236, 16)
        _draw_rounded_rect_aa(buf, width, height, 92 + offset_x, 76, 128, 84, 12, soft_accent)
        _draw_circle_aa(buf, width, height, 156 + offset_x, 118, 28, accent_base, alpha=0.85)
        _draw_circle_aa(buf, width, height, 134 + offset_x, 132, 16, (255, 255, 255), alpha=0.55)
        for row_i in range(3):
            w_bar = 122 - ((var + row_i) % 3) * 24
            _draw_rounded_rect_aa(buf, width, height, 238 + offset_x, 82 + row_i * 26, w_bar, 12, 6, muted_line if row_i else accent_base)
        # Artboard grid preview tiles
        for tile_i in range(4):
            tx = 92 + offset_x + tile_i * 70
            _draw_rounded_rect_aa(buf, width, height, tx, 180, 58, 90, 10, subtle_line if tile_i != (var + slide_index) % 4 else soft_accent)
            _draw_circle_aa(buf, width, height, tx + 29, 214, 13, accent_base if tile_i % 2 == 0 else mid_accent, alpha=0.8)
        # Floating color swatch card
        _draw_card_with_border(buf, width, height, 344 - slide_index * 16, 174 + (var % 2) * 14, 214, 164, 16)
        swatches = [accent_base, mid_accent, soft_accent, dark_slate]
        for s_i, sw in enumerate(swatches):
            _draw_circle_aa(buf, width, height, 382 - slide_index * 16 + s_i * 44, 224 + (var % 2) * 14, 16, sw)
        _draw_line_aa(buf, width, height, 368 - slide_index * 16, 296, 420 - slide_index * 16, 266, 3.0, accent_base)
        _draw_line_aa(buf, width, height, 420 - slide_index * 16, 266, 488 - slide_index * 16, 306, 3.0, accent_base)
        _draw_circle_aa(buf, width, height, 420 - slide_index * 16, 266, 5.5, (255, 255, 255))
        _draw_ring_aa(buf, width, height, 420 - slide_index * 16, 266, 5.5, 2.2, accent_base)

    elif cat_slug == "documents-and-productivity":
        # Clean layered SaaS sheets, checklist pills & calendar blocks
        _draw_card_with_border(buf, width, height, 118 - slide_index * 8, 48, 286, 304, 16, fill=(248, 250, 252))
        _draw_card_with_border(buf, width, height, 84 + var * 6, 68, 296, 284, 16)
        _draw_rounded_rect_aa(buf, width, height, 108 + var * 6, 92, 116, 14, 7, accent_base)
        _draw_rounded_rect_aa(buf, width, height, 108 + var * 6, 116, 196, 8, 4, muted_line)
        for idx_r in range(5):
            ry = 148 + idx_r * 36
            checked = (idx_r + var + slide_index) % 2 == 0
            _draw_circle_aa(buf, width, height, 120 + var * 6, ry + 7, 9, accent_base if checked else muted_line)
            if checked:
                _draw_circle_aa(buf, width, height, 120 + var * 6, ry + 7, 3.5, (255, 255, 255))
            bar_w = 180 - ((idx_r * 23 + var * 17) % 60)
            _draw_rounded_rect_aa(buf, width, height, 142 + var * 6, ry + 2, bar_w, 10, 5, soft_accent if checked else muted_line)
        # Right Kanban / tracker card
        _draw_card_with_border(buf, width, height, 404, 88 + slide_index * 14, 174, 240, 16)
        for row_c in range(3):
            for col_c in range(3):
                cx = 424 + col_c * 46
                cy = 114 + slide_index * 14 + row_c * 44
                active_cell = (row_c + col_c + var) % 3 == 0
                _draw_rounded_rect_aa(buf, width, height, cx, cy, 38, 34, 8, accent_base if active_cell else subtle_line)
        _draw_rounded_rect_aa(buf, width, height, 424, 260 + slide_index * 14, 132, 12, 6, soft_accent)
        _draw_rounded_rect_aa(buf, width, height, 424, 260 + slide_index * 14, 86 + var * 8, 12, 6, accent_base)

    elif cat_slug == "education-and-learning":
        # Open dual-page study spread + curve plot + chapter progress cards
        _draw_card_with_border(buf, width, height, 70, 58, 498, 284, 18)
        _draw_rect(buf, width, height, 319, 70, 2, 260, muted_line)
        # Left page: chapter cards & ribbon bookmark
        _draw_rounded_rect_aa(buf, width, height, 100, 48, 24, 48, 6, accent_base)
        _draw_rounded_rect_aa(buf, width, height, 100, 114, 184, 14, 7, dark_slate)
        for l_i in range(4):
            lw = 178 - ((l_i + var) % 3) * 32
            _draw_rounded_rect_aa(buf, width, height, 100, 146 + l_i * 22, lw, 9, 4, muted_line)
        _draw_rounded_rect_aa(buf, width, height, 100, 248, 188, 66, 12, soft_accent)
        _draw_circle_aa(buf, width, height, 132, 281, 16, accent_base)
        _draw_rounded_rect_aa(buf, width, height, 162, 270, 96, 10, 5, dark_slate)
        _draw_rounded_rect_aa(buf, width, height, 162, 288, 72, 8, 4, mid_accent)
        # Right page: interactive curve plot + milestone rings
        _draw_rounded_rect_aa(buf, width, height, 346, 88, 194, 132, 12, subtle_line)
        pts = [(364 + i * 26, 188 - int(44 * math.sin((i + var + slide_index) * 0.65) + 28)) for i in range(7)]
        for p_a, p_b in zip(pts, pts[1:]):
            _draw_line_aa(buf, width, height, p_a[0], p_a[1], p_b[0], p_b[1], 3.5, accent_base)
        for p_x, p_y in pts[::2]:
            _draw_circle_aa(buf, width, height, p_x, p_y, 5.5, (255, 255, 255))
            _draw_ring_aa(buf, width, height, p_x, p_y, 5.5, 2.5, accent_base)
        for b_i in range(3):
            _draw_ring_aa(buf, width, height, 382 + b_i * 60, 276, 20, 6.0, muted_line)
            _draw_circle_aa(buf, width, height, 382 + b_i * 60, 276, 11, accent_base if (b_i + slide_index) % 2 == 0 else mid_accent)

    elif cat_slug == "development-and-technology":
        # Crisp IDE / code window + component tree floating panel
        _draw_card_with_border(buf, width, height, 68, 54, 412, 274, 16, fill=(15, 23, 42), border=(30, 41, 59))
        _draw_circle_aa(buf, width, height, 94, 78, 5.5, (244, 63, 94))
        _draw_circle_aa(buf, width, height, 114, 78, 5.5, (245, 158, 11))
        _draw_circle_aa(buf, width, height, 134, 78, 5.5, (34, 197, 94))
        _draw_rect(buf, width, height, 69, 98, 410, 1, (30, 41, 59))
        code_colors = [accent_base, (56, 189, 248), (167, 139, 250), (52, 211, 153)]
        for row_k in range(7):
            indent = ((row_k + var) % 3) * 24
            y_pos = 120 + row_k * 27
            seg1 = 68 + ((row_k * 19 + var * 13) % 48)
            seg2 = 84 + ((row_k * 11 + slide_index * 17) % 72)
            _draw_rounded_rect_aa(buf, width, height, 94 + indent, y_pos, seg1, 11, 5, code_colors[(row_k + var) % len(code_colors)])
            _draw_rounded_rect_aa(buf, width, height, 94 + indent + seg1 + 12, y_pos, seg2, 11, 5, (71, 85, 105))
        # Floating component preview card
        _draw_card_with_border(buf, width, height, 386 + slide_index * 8, 164, 196, 178, 16)
        _draw_rounded_rect_aa(buf, width, height, 408 + slide_index * 8, 188, 152, 54, 10, soft_accent)
        _draw_circle_aa(buf, width, height, 434 + slide_index * 8, 215, 14, accent_base)
        _draw_rounded_rect_aa(buf, width, height, 458 + slide_index * 8, 206, 82, 8, 4, dark_slate)
        _draw_rounded_rect_aa(buf, width, height, 458 + slide_index * 8, 220, 54, 7, 3, mid_accent)
        _draw_rounded_rect_aa(buf, width, height, 408 + slide_index * 8, 260, 152, 28, 8, accent_base)
        _draw_rounded_rect_aa(buf, width, height, 408 + slide_index * 8, 300, 106, 10, 5, muted_line)

    elif cat_slug == "ai-resources-and-automation":
        # Connected workflow node graph + prompt cards
        _draw_card_with_border(buf, width, height, 68, 52, 504, 296, 18)
        nodes = [
            (156, 140 + (var % 2) * 16),
            (156, 260 - (var % 2) * 16),
            (320, 200),
            (484, 128 + slide_index * 12),
            (484, 272 - slide_index * 12),
        ]
        edges = [(0, 2), (1, 2), (2, 3), (2, 4), (0, 3)]
        for a_i, b_i in edges:
            _draw_line_aa(buf, width, height, nodes[a_i][0], nodes[a_i][1], nodes[b_i][0], nodes[b_i][1], 3.5, mid_accent, alpha=0.8)
        # Node pills
        for n_i, (nx, ny) in enumerate(nodes):
            rad = 34 if n_i == 2 else 26
            _draw_circle_aa(buf, width, height, nx, ny, rad + 6, soft_accent, alpha=0.95)
            _draw_circle_aa(buf, width, height, nx, ny, rad - 2, accent_base if n_i == 2 or (n_i + var) % 2 == 0 else dark_slate)
            _draw_circle_aa(buf, width, height, nx, ny, 9 if n_i == 2 else 7, (255, 255, 255))
        # Subtle side prompt pill bars
        _draw_rounded_rect_aa(buf, width, height, 98, 76, 148, 12, 6, soft_accent)
        _draw_rounded_rect_aa(buf, width, height, 98, 76, 92 + var * 10, 12, 6, accent_base)
        _draw_rounded_rect_aa(buf, width, height, 392, 308, 142, 10, 5, muted_line)

    elif cat_slug == "digital-marketing":
        # Campaign analytics chart + trend polyline + social feed cards
        _draw_card_with_border(buf, width, height, 66, 56, 336, 286, 16)
        _draw_rounded_rect_aa(buf, width, height, 92, 82, 108, 12, 6, accent_base)
        _draw_rounded_rect_aa(buf, width, height, 92, 104, 164, 8, 4, muted_line)
        bars = [74, 108, 92, 138, 166, 152]
        line_pts = []
        for b_idx, bh in enumerate(bars):
            adj_h = max(44, min(176, bh + ((var * 17 + b_idx * 13 + slide_index * 11) % 34) - 16))
            bx = 96 + b_idx * 46
            by = 304 - adj_h
            _draw_rounded_rect_aa(buf, width, height, bx, by, 28, adj_h, 8, accent_base if b_idx >= 4 else soft_accent)
            line_pts.append((bx + 14, by - 14))
        for p1, p2 in zip(line_pts, line_pts[1:]):
            _draw_line_aa(buf, width, height, p1[0], p1[1], p2[0], p2[1], 3.0, dark_slate)
        for lx, ly in line_pts:
            _draw_circle_aa(buf, width, height, lx, ly, 4.5, accent_base)
        # Right campaign feed frame
        _draw_card_with_border(buf, width, height, 424, 72 + slide_index * 10, 152, 246, 16)
        _draw_rounded_rect_aa(buf, width, height, 442, 92 + slide_index * 10, 116, 102, 12, soft_accent)
        _draw_circle_aa(buf, width, height, 500, 143 + slide_index * 10, 26, accent_base)
        _draw_rounded_rect_aa(buf, width, height, 442, 210 + slide_index * 10, 96, 10, 5, dark_slate)
        _draw_rounded_rect_aa(buf, width, height, 442, 232 + slide_index * 10, 116, 8, 4, muted_line)
        _draw_rounded_rect_aa(buf, width, height, 442, 264 + slide_index * 10, 72, 24, 8, accent_base)

    elif cat_slug == "audio-and-video":
        # Equalizer studio card + timeline track + play ring
        _draw_card_with_border(buf, width, height, 68, 56, 504, 288, 18, fill=(24, 24, 27), border=(63, 63, 70))
        # Equalizer spectrum bars
        eq_count = 18
        for eq_i in range(eq_count):
            amp = 26 + int(74 * abs(math.sin((eq_i + 1) * 0.45 + var * 0.7 + slide_index * 0.5)))
            bx = 104 + eq_i * 24
            by = 164 - amp // 2
            bar_col = accent_base if eq_i % 3 != 0 else (251, 191, 36)
            _draw_rounded_rect_aa(buf, width, height, bx, by, 13, amp, 6, bar_col)
        # Timeline playhead track
        _draw_rounded_rect_aa(buf, width, height, 104, 256, 432, 10, 5, (63, 63, 70))
        progress_w = 140 + (var * 55 + slide_index * 45) % 240
        _draw_rounded_rect_aa(buf, width, height, 104, 256, progress_w, 10, 5, accent_base)
        _draw_circle_aa(buf, width, height, 104 + progress_w, 261, 10, (255, 255, 255))
        _draw_circle_aa(buf, width, height, 104 + progress_w, 261, 4.5, accent_base)
        # Bottom video clip blocks
        for clip_i in range(4):
            cx = 104 + clip_i * 110
            _draw_rounded_rect_aa(buf, width, height, cx, 286, 98, 28, 8, (39, 39, 42) if clip_i != slide_index else accent_base)

    else:
        # Business Resources: pitch slide stack, executive KPI ring & revenue stairs
        _draw_card_with_border(buf, width, height, 92, 48, 456, 260, 16, fill=(248, 250, 252))
        _draw_card_with_border(buf, width, height, 72, 68, 496, 280, 16)
        _draw_rounded_rect_aa(buf, width, height, 104, 96, 136, 14, 7, dark_slate)
        _draw_rounded_rect_aa(buf, width, height, 104, 120, 200, 9, 4, muted_line)
        # Revenue growth staircase
        for st_i in range(5):
            st_h = 34 + st_i * 22 + ((var + slide_index) % 3) * 8
            sx = 108 + st_i * 48
            sy = 308 - st_h
            _draw_rounded_rect_aa(buf, width, height, sx, sy, 34, st_h, 8, accent_base if st_i >= 3 else soft_accent)
        # Right KPI donut & breakdown
        cx, cy = 448, 198
        _draw_ring_aa(buf, width, height, cx, cy, 58, 18, subtle_line)
        _draw_ring_aa(buf, width, height, cx, cy, 58, 18, accent_base, alpha=0.92)
        _draw_circle_aa(buf, width, height, cx, cy, 22, soft_accent)
        _draw_rounded_rect_aa(buf, width, height, 384, 290, 128, 12, 6, muted_line)
        _draw_rounded_rect_aa(buf, width, height, 384, 290, 74 + var * 10, 12, 6, accent_base)

    return _encode_png_rgb(width, height, buf)


# ---------------------------------------------------------------------------
# Idempotent Seeding Execution
# ---------------------------------------------------------------------------


def _ensure_demo_seller(db: Session, spec: DemoSellerSpec, stats: SeedStats) -> SellerProfile:
    existing_seller = db.scalar(
        select(SellerProfile).where(SellerProfile.store_slug == spec.store_slug)
    )
    if existing_seller:
        stats.sellers_existing += 1
        return existing_seller

    customer = db.scalar(select(Customer).where(func.lower(Customer.email) == spec.email.lower()))
    if not customer:
        customer = Customer(
            full_name=f"{spec.store_name} (Demo)",
            email=spec.email,
            phone_number=None,
            password_hash=get_password_hash(secrets.token_urlsafe(32)),
            is_email_verified=True,
            is_phone_verified=True,
            account_status=AccountStatus.ACTIVE,
            email_marketing_consent=False,
            whatsapp_marketing_consent=False,
        )
        db.add(customer)
        db.flush()

    now = datetime.now(timezone.utc)
    seller = SellerProfile(
        customer_id=customer.id,
        store_name=spec.store_name,
        store_slug=spec.store_slug,
        seller_display_name=spec.seller_display_name,
        store_description=f"[DEMO STOREFRONT] {spec.tagline} ({DEMO_DISCLAIMER})",
        application_description=f"Synthetic demo creator storefront ({DEMO_DISCLAIMER}).",
        contact_email=spec.email,
        contact_info=None,
        country=spec.country,
        business_type=spec.business_type,
        product_categories=list(spec.categories),
        application_status=SellerApplicationStatus.APPROVED,
        approved_at=now,
        approved_by_admin_id=None,
    )
    db.add(seller)
    db.flush()
    stats.sellers_created += 1
    return seller


def _ensure_category(db: Session, spec: DemoCategorySpec, stats: SeedStats) -> Category:
    existing = db.scalar(
        select(Category).where((Category.slug == spec.slug) | (func.lower(Category.name) == spec.name.lower()))
    )
    if existing:
        stats.categories_existing += 1
        return existing
    cat = Category(
        name=spec.name,
        slug=spec.slug,
        description=spec.description,
        is_active=True,
    )
    db.add(cat)
    db.flush()
    stats.categories_created += 1
    return cat


def _make_upload_file(filename: str, data: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def _format_human_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def seed_demo_catalog(db: Session, *, allow_test_db: bool = False) -> SeedStats:
    """Idempotently populate 4 demo sellers, 8 categories, 32 products, 32 assets, and 96 PNGs."""
    active_db = verify_seed_target(db, allow_test_db=allow_test_db)
    stats = SeedStats(database_name=active_db)
    now = datetime.now(timezone.utc)

    seller_map: dict[str, SellerProfile] = {}
    for s_spec in DEMO_SELLERS:
        seller_map[s_spec.store_slug] = _ensure_demo_seller(db, s_spec, stats)

    category_map: dict[str, Category] = {}
    category_spec_map: dict[str, DemoCategorySpec] = {}
    for c_spec in DEMO_CATEGORIES:
        category_map[c_spec.slug] = _ensure_category(db, c_spec, stats)
        category_spec_map[c_spec.slug] = c_spec

    storage = get_asset_storage()

    for idx, p_spec in enumerate(DEMO_PRODUCTS):
        cat = category_map[p_spec.category_slug]
        cat_spec = category_spec_map[p_spec.category_slug]
        seller = seller_map[p_spec.seller_slug] if p_spec.seller_slug else None

        asset_filename, asset_bytes, asset_mime = build_demo_asset_bytes(p_spec, idx)
        public_meta = {
            "format": p_spec.asset_ext.lstrip(".").upper(),
            "file_size": _format_human_size(len(asset_bytes)),
            "version": "1.0.0-demo",
            "license": "Demo Preview License",
            "tags": list(p_spec.tags),
            "demo_seed": True,
            "includes": list(p_spec.includes),
            "notice": DEMO_DISCLAIMER,
        }

        product = db.scalar(select(Product).where(Product.slug == p_spec.slug))
        if not product:
            product = Product(
                name=p_spec.name,
                slug=p_spec.slug,
                category_id=cat.id,
                seller_id=seller.id if seller else None,
                approval_status=ProductApprovalStatus.PUBLISHED,
                reviewed_at=now,
                reviewed_by_admin_id=None,
                short_description=p_spec.short_description,
                main_description=p_spec.main_description,
                detailed_description=p_spec.detailed_description,
                original_price=p_spec.original_price,
                product_type=p_spec.product_type,
                product_metadata=public_meta,
                is_on_sale=bool(p_spec.sale_price is not None),
                is_active=True,
            )
            db.add(product)
            db.flush()
            stats.products_created += 1
        else:
            changed = False
            if product.approval_status != ProductApprovalStatus.PUBLISHED:
                product.approval_status = ProductApprovalStatus.PUBLISHED
                product.reviewed_at = product.reviewed_at or now
                changed = True
            if not product.is_active:
                product.is_active = True
                changed = True
            if product.product_metadata != public_meta:
                product.product_metadata = public_meta
                changed = True
            if changed:
                stats.products_updated += 1
            else:
                stats.products_existing += 1

        # Promotional sale window (if specified and no live sale exists)
        if p_spec.sale_price is not None:
            active_sale = db.scalar(
                select(Sale).where(Sale.product_id == product.id, Sale.is_active.is_(True))
            )
            if not active_sale:
                db.add(
                    Sale(
                        product_id=product.id,
                        original_price_snapshot=product.original_price,
                        discounted_price=p_spec.sale_price,
                        starts_at=now - timedelta(minutes=5),
                        expires_at=now + timedelta(days=DEMO_DISCOUNT_DURATION_DAYS),
                        is_active=True,
                    )
                )
                product.is_on_sale = True
                stats.sales_created += 1

        # Private digital asset upload via canonical validation & storage provider
        if not product.asset_storage_key:
            spooled = validate_and_spool_asset_upload(
                _make_upload_file(asset_filename, asset_bytes, asset_mime),
                product_id=product.id,
            )
            try:
                stored_meta = storage.save(
                    file_obj=spooled.spool,
                    storage_key=spooled.storage_key,
                    content_type=spooled.content_type,
                    size_bytes=spooled.size_bytes,
                    sha256_hex=spooled.sha256,
                )
                product.asset_storage_backend = stored_meta.storage_backend
                product.asset_storage_key = stored_meta.storage_key
                product.asset_original_filename = spooled.display_filename
                product.asset_content_type = spooled.content_type
                product.asset_size_bytes = stored_meta.size_bytes
                product.asset_sha256 = spooled.sha256
                product.asset_uploaded_at = now
                product.private_download_url = "asset://managed"
                db.flush()
                stats.assets_uploaded += 1
            finally:
                spooled.close()
        else:
            stats.assets_skipped += 1

        # 3 unique 640x400 PNG images (1 primary + 2 previews) via image storage service
        existing_images = db.scalars(
            select(ProductImage)
            .where(ProductImage.product_id == product.id)
            .order_by(ProductImage.display_order.asc())
        ).all()
        if len(existing_images) < 3:
            existing_orders = {img.display_order for img in existing_images}
            for slide_idx in range(3):
                if slide_idx in existing_orders:
                    continue
                png_bytes = build_product_png(p_spec, cat_spec, idx, slide_idx)
                stats.image_hashes.add(hashlib.sha256(png_bytes).hexdigest())
                upload = _make_upload_file(f"{p_spec.slug}-{slide_idx}.png", png_bytes, "image/png")
                upload_product_image(
                    db=db,
                    admin=None,
                    product_id=product.id,
                    file=upload,
                    display_order=slide_idx,
                    is_primary=(slide_idx == 0),
                )
                stats.images_uploaded += 1
        else:
            stats.images_skipped += len(existing_images)

    db.flush()
    return stats


def refresh_demo_product_images(db: Session, *, allow_test_db: bool = False) -> dict[str, Any]:
    """Replace existing demo product PNG artwork in-place without creating new DB records."""
    active_db = verify_seed_target(db, allow_test_db=allow_test_db)
    cat_spec_map = {c.slug: c for c in DEMO_CATEGORIES}
    replaced = 0
    seen_hashes: set[str] = set()

    for idx, p_spec in enumerate(DEMO_PRODUCTS):
        product = db.scalar(select(Product).where(Product.slug == p_spec.slug))
        if not product:
            continue
        cat_spec = cat_spec_map[p_spec.category_slug]
        images = db.scalars(
            select(ProductImage)
            .where(ProductImage.product_id == product.id)
            .order_by(ProductImage.display_order.asc())
        ).all()
        for img in images:
            slide_idx = min(2, max(0, img.display_order))
            png_bytes = build_product_png(p_spec, cat_spec, idx, slide_idx)
            seen_hashes.add(hashlib.sha256(png_bytes).hexdigest())
            upload = _make_upload_file(f"{p_spec.slug}-{slide_idx}.png", png_bytes, "image/png")
            replace_product_image(
                db=db,
                admin=None,
                product_id=product.id,
                image_id=img.id,
                file=upload,
            )
            replaced += 1

    db.flush()
    return {
        "database": active_db,
        "images_replaced": replaced,
        "unique_image_hashes": len(seen_hashes),
    }


def main() -> int:
    refresh_only = "--refresh-images" in sys.argv[1:]
    url_obj = make_url(settings.DATABASE_URL)
    if (url_obj.database or "").strip() != "digiverse_local":
        raise SystemExit(
            f"Refusing to run CLI seeder: DATABASE_URL targets '{url_obj.database}', expected 'digiverse_local'."
        )
    db = SessionLocal()
    try:
        if refresh_only:
            result = refresh_demo_product_images(db, allow_test_db=False)
        else:
            result = seed_demo_catalog(db, allow_test_db=False).summary_dict()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
