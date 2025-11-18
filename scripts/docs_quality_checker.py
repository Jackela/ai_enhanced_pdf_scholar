#!/usr/bin/env python3
"""
Documentation Quality Checker

This script analyzes documentation quality across multiple dimensions including
completeness, consistency, readability, and maintainability.

Usage:
    python scripts/docs_quality_checker.py [--format json|html|text] [--output report.html]
"""

import argparse
import json
import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class QualityMetric:
    """Represents a single quality metric."""

    name: str
    score: float  # 0.0 to 1.0
    max_score: float = 1.0
    weight: float = 1.0
    details: dict[str, Any] = None
    issues: list[str] = None

    def __post_init__(self) -> None:
        if self.details is None:
            self.details = {}
        if self.issues is None:
            self.issues = []

    @property
    def percentage(self) -> float:
        return (self.score / self.max_score) * 100 if self.max_score > 0 else 0

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class DocumentAnalysis:
    """Analysis results for a single document."""

    file_path: str
    title: str
    word_count: int
    readability_score: float
    completeness_score: float
    consistency_score: float
    structure_score: float
    link_score: float
    code_example_count: int
    diagram_count: int
    last_modified: str
    issues: list[str]

    @property
    def overall_score(self) -> float:
        scores = [
            self.readability_score,
            self.completeness_score,
            self.consistency_score,
            self.structure_score,
            self.link_score,
        ]
        return statistics.mean(scores)


@dataclass
class QualityReport:
    """Complete quality assessment report."""

    overall_score: float
    metrics: dict[str, QualityMetric]
    documents: list[DocumentAnalysis]
    summary: dict[str, Any]
    recommendations: list[str]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "metrics": {k: asdict(v) for k, v in self.metrics.items()},
            "documents": [asdict(doc) for doc in self.documents],
            "summary": self.summary,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at,
        }


class DocumentationQualityChecker:
    """Comprehensive documentation quality assessment tool."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self.docs_dir = self.project_root / "docs"

        # Quality thresholds
        self.thresholds = {"excellent": 0.9, "good": 0.75, "fair": 0.6, "poor": 0.4}

        # Word lists for analysis
        self.technical_terms = set()
        self.load_technical_terms()

        # Readability parameters
        self.avg_sentence_length_target = 20
        self.avg_word_length_target = 5

        print("📊 Documentation Quality Checker initialized")
        print(f"   Project: {self.project_root}")
        print(f"   Docs Dir: {self.docs_dir}")

    def load_technical_terms(self) -> None:
        """Load project-specific technical terms for analysis."""
        terms = {
            # AI/ML terms
            "rag",
            "llm",
            "embedding",
            "vector",
            "semantic",
            "neural",
            "transformer",
            "attention",
            "inference",
            "training",
            "model",
            "prompt",
            "completion",
            # Technical terms
            "api",
            "rest",
            "endpoint",
            "json",
            "yaml",
            "http",
            "https",
            "websocket",
            "kubernetes",
            "docker",
            "container",
            "microservice",
            "database",
            "sql",
            "cache",
            "redis",
            "postgresql",
            "sqlite",
            "fastapi",
            "uvicorn",
            # PDF/Document terms
            "pdf",
            "document",
            "citation",
            "reference",
            "bibliography",
            "metadata",
            "extraction",
            "parsing",
            "ocr",
            "text",
            "annotation",
        }
        self.technical_terms.update(terms)

    def analyze_all_documents(self) -> QualityReport:
        """Perform comprehensive quality analysis on all documentation."""
        print("🔍 Starting comprehensive documentation quality analysis...")

        # Find all markdown files
        md_files = list(self.docs_dir.rglob("*.md"))
        readme_files = list(self.project_root.glob("*.md"))
        all_files = md_files + readme_files

        print(f"   Found {len(all_files)} documentation files")

        # Analyze each document
        document_analyses = []
        for file_path in all_files:
            try:
                analysis = self.analyze_document(file_path)
                document_analyses.append(analysis)
                print(f"   ✅ Analyzed: {file_path.relative_to(self.project_root)}")
            except Exception as e:
                print(f"   ❌ Error analyzing {file_path}: {e}")

        # Calculate overall metrics
        metrics = self.calculate_overall_metrics(document_analyses)

        # Generate recommendations
        recommendations = self.generate_recommendations(document_analyses, metrics)

        # Create summary
        summary = self.create_summary(document_analyses, metrics)

        # Calculate overall score
        overall_score = statistics.mean([m.score for m in metrics.values()])

        report = QualityReport(
            overall_score=overall_score,
            metrics=metrics,
            documents=document_analyses,
            summary=summary,
            recommendations=recommendations,
            generated_at=datetime.now().isoformat(),
        )

        print(
            f"✅ Quality analysis completed. Overall score: {overall_score:.2f} ({self.get_quality_grade(overall_score)})"
        )

        return report

    def analyze_document(self, file_path: Path) -> DocumentAnalysis:
        """Analyze quality metrics for a single document."""
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Extract metadata
        title = self.extract_title(content)
        word_count = len(content.split())
        last_modified = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()

        # Analyze different quality dimensions
        readability = self.analyze_readability(content)
        completeness = self.analyze_completeness(content, file_path)
        consistency = self.analyze_consistency(content)
        structure = self.analyze_structure(content)
        links = self.analyze_links(content, file_path)

        # Count special elements
        code_examples = len(re.findall(r"```[\s\S]*?```", content))
        diagrams = len(re.findall(r"```mermaid[\s\S]*?```", content))

        # Collect issues
        issues = []
        if readability < 0.6:
            issues.append("Low readability score - consider simplifying language")
        if completeness < 0.7:
            issues.append("Document appears incomplete or lacks essential sections")
        if consistency < 0.8:
            issues.append("Inconsistent formatting or terminology")
        if structure < 0.7:
            issues.append(
                "Poor document structure - consider adding headers and organization"
            )
        if links < 0.9:
            issues.append("Broken or problematic links detected")
        if word_count < 100:
            issues.append("Document is very short - consider adding more detail")
        if code_examples == 0 and "api" in str(file_path).lower():
            issues.append("API documentation lacks code examples")

        return DocumentAnalysis(
            file_path=str(file_path.relative_to(self.project_root)),
            title=title,
            word_count=word_count,
            readability_score=readability,
            completeness_score=completeness,
            consistency_score=consistency,
            structure_score=structure,
            link_score=links,
            code_example_count=code_examples,
            diagram_count=diagrams,
            last_modified=last_modified,
            issues=issues,
        )

    def analyze_readability(self, content: str) -> float:
        """Analyze document readability using multiple metrics."""
        # Remove code blocks and markdown syntax for analysis
        clean_content = re.sub(r"```[\s\S]*?```", "", content)
        clean_content = re.sub(r"`[^`]*`", "", clean_content)
        clean_content = re.sub(r"#{1,6}\s+", "", clean_content)
        clean_content = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", clean_content)

        sentences = [s.strip() for s in re.split(r"[.!?]+", clean_content) if s.strip()]
        if not sentences:
            return 0.5

        words = clean_content.split()
        if not words:
            return 0.5

        # Calculate basic metrics
        avg_sentence_length = len(words) / len(sentences)
        avg_word_length = statistics.mean(len(word) for word in words)

        # Count complex words (3+ syllables, simplified heuristic)
        complex_words = sum(1 for word in words if self.count_syllables(word) >= 3)
        complex_word_ratio = complex_words / len(words)

        # Simplified Flesch Reading Ease approximation
        flesch_score = (
            206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_word_length / 4.7)
        )
        flesch_normalized = max(0, min(100, flesch_score)) / 100

        # Technical writing adjustments
        technical_term_ratio = sum(
            1 for word in words if word.lower() in self.technical_terms
        ) / len(words)
        technical_bonus = min(
            0.2, technical_term_ratio * 0.5
        )  # Bonus for appropriate technical terms

        # Sentence length score (penalize very long sentences)
        sentence_length_score = max(
            0, 1 - (max(0, avg_sentence_length - self.avg_sentence_length_target) / 30)
        )

        # Combine metrics
        readability_score = (
            flesch_normalized * 0.4
            + sentence_length_score * 0.3
            + (1 - complex_word_ratio) * 0.2
            + technical_bonus * 0.1
        )

        return max(0, min(1, readability_score))

    def count_syllables(self, word: str) -> int:
        """Estimate syllable count using simple heuristics."""
        word = word.lower().strip()
        if len(word) <= 3:
            return 1

        vowels = "aeiouy"
        syllable_count = 0
        prev_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            prev_was_vowel = is_vowel

        # Handle silent 'e'
        if word.endswith("e") and syllable_count > 1:
            syllable_count -= 1

        return max(1, syllable_count)

    def analyze_completeness(self, content: str, file_path: Path) -> float:
        """Analyze document completeness based on expected sections."""
        file_name = file_path.name.lower()

        # Define expected sections for different document types
        expected_sections = {}

        if "readme" in file_name:
            expected_sections = {
                "installation": 0.2,
                "usage": 0.2,
                "features": 0.15,
                "getting started": 0.15,
                "documentation": 0.1,
                "contributing": 0.1,
                "license": 0.08,
            }
        elif "api" in file_name:
            expected_sections = {
                "endpoints": 0.25,
                "authentication": 0.15,
                "parameters": 0.15,
                "responses": 0.15,
                "examples": 0.15,
                "error": 0.1,
                "rate limit": 0.05,
            }
        elif "getting-started" in file_name or "quick-start" in file_name:
            expected_sections = {
                "prerequisites": 0.2,
                "installation": 0.25,
                "configuration": 0.2,
                "first steps": 0.2,
                "examples": 0.15,
            }
        elif "deployment" in file_name:
            expected_sections = {
                "requirements": 0.15,
                "configuration": 0.2,
                "deployment": 0.25,
                "monitoring": 0.15,
                "troubleshooting": 0.15,
                "security": 0.1,
            }
        elif "architecture" in file_name:
            expected_sections = {
                "overview": 0.2,
                "components": 0.2,
                "data flow": 0.15,
                "security": 0.15,
                "scalability": 0.15,
                "diagrams": 0.15,
            }
        else:
            # Generic documentation expectations
            expected_sections = {
                "introduction": 0.2,
                "usage": 0.3,
                "examples": 0.2,
                "configuration": 0.15,
                "troubleshooting": 0.15,
            }

        # Score based on section presence
        content_lower = content.lower()
        total_score = 0

        for section, weight in expected_sections.items():
            # Look for section headers or keywords
            section_patterns = [
                f"#{1,6}.*{section}",
                f"## {section}",
                f"{section}:",
                f"{section} section",
            ]

            found = any(
                re.search(pattern, content_lower) for pattern in section_patterns
            )
            if found:
                total_score += weight

            # Partial credit for related keywords
            elif any(keyword in content_lower for keyword in section.split()):
                total_score += weight * 0.5

        # Bonus for comprehensive content
        word_count = len(content.split())
        if word_count > 1000:
            total_score += 0.1  # Bonus for detailed documentation

        # Penalty for very short content
        if word_count < 200:
            total_score *= 0.7

        return max(0, min(1, total_score))

    def analyze_consistency(self, content: str) -> float:
        """Analyze document consistency in formatting and terminology."""
        issues = []

        # Check header consistency
        headers = re.findall(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE)
        if headers:
            # Check for consistent header formatting
            header_styles = Counter()
            for level, text in headers:
                # Check title case consistency
                is_title_case = text.strip().istitle()
                is_sentence_case = (
                    text.strip()[0].isupper() and not text.strip().istitle()
                )

                if is_title_case:
                    header_styles["title"] += 1
                elif is_sentence_case:
                    header_styles["sentence"] += 1
                else:
                    header_styles["mixed"] += 1

            # Penalize if mixed styles
            if len(header_styles) > 1:
                issues.append("Inconsistent header capitalization")

        # Check link formatting consistency
        links = re.findall(r"\[([^\]]*)\]\(([^\)]*)\)", content)
        relative_links = [
            link for _, link in links if not link.startswith(("http", "mailto:"))
        ]
        if relative_links:
            # Check for consistent relative link patterns
            link_patterns = set()
            for link in relative_links:
                if link.startswith("./"):
                    link_patterns.add("relative_dot")
                elif link.startswith("/"):
                    link_patterns.add("absolute")
                else:
                    link_patterns.add("relative")

            if len(link_patterns) > 1:
                issues.append("Inconsistent link formatting")

        # Check code block consistency
        code_blocks = re.findall(r"```(\w*)\n", content)
        if code_blocks:
            # Check for language specification consistency
            with_lang = sum(1 for lang in code_blocks if lang.strip())
            without_lang = len(code_blocks) - with_lang

            if without_lang > 0 and with_lang > 0:
                issues.append("Inconsistent code block language specification")

        # Check list formatting consistency
        bullet_lists = re.findall(r"^[\s]*[-*+]\s", content, re.MULTILINE)
        if bullet_lists:
            bullet_types = set(match.strip()[-1] for match in bullet_lists)
            if len(bullet_types) > 1:
                issues.append("Inconsistent bullet point formatting")

        # Check terminology consistency (case sensitivity)
        technical_terms_found = []
        words = re.findall(r"\b\w+\b", content.lower())
        for word in set(words):
            if word in self.technical_terms:
                # Find all instances of this term with their original case
                instances = re.findall(
                    r"\b" + re.escape(word) + r"\b", content, re.IGNORECASE
                )
                if len(set(instances)) > 1:  # Multiple different capitalizations
                    technical_terms_found.append(word)

        if technical_terms_found:
            issues.append(
                f"Inconsistent capitalization of terms: {', '.join(technical_terms_found[:3])}"
            )

        # Calculate consistency score
        consistency_score = 1.0 - (
            len(issues) * 0.15
        )  # Each issue reduces score by 15%
        return max(0, min(1, consistency_score))

    def analyze_structure(self, content: str) -> float:
        """Analyze document structure and organization."""
        lines = content.split("\n")

        # Check for table of contents
        has_toc = any(
            re.search(r"table of contents|toc", line, re.IGNORECASE) for line in lines
        )

        # Analyze header hierarchy
        headers = []
        for line in lines:
            match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if match:
                level = len(match.group(1))
                text = match.group(2)
                headers.append((level, text))

        structure_score = 0

        # Base score for having headers
        if headers:
            structure_score += 0.3

            # Check for logical header progression
            if len(headers) > 1:
                logical_progression = True
                prev_level = headers[0][0]

                for level, _ in headers[1:]:
                    # Allow same level or one level deeper
                    if level > prev_level + 1:
                        logical_progression = False
                        break
                    prev_level = level

                if logical_progression:
                    structure_score += 0.2

            # Bonus for having multiple levels
            unique_levels = len(set(level for level, _ in headers))
            if unique_levels >= 2:
                structure_score += 0.15

        # Check for introduction section
        first_section = headers[0][1].lower() if headers else ""
        if any(
            keyword in first_section
            for keyword in ["overview", "introduction", "about"]
        ):
            structure_score += 0.1

        # Check for conclusion or summary
        last_section = headers[-1][1].lower() if headers else ""
        if any(
            keyword in last_section
            for keyword in ["conclusion", "summary", "next steps"]
        ):
            structure_score += 0.1

        # Bonus for table of contents
        if has_toc and len(headers) > 3:
            structure_score += 0.15

        return max(0, min(1, structure_score))

    def analyze_links(self, content: str, file_path: Path) -> float:
        """Analyze link quality and validity."""
        links = re.findall(r"\[([^\]]*)\]\(([^\)]*)\)", content)

        if not links:
            return 1.0  # No links to break

        valid_links = 0
        total_links = len(links)

        for text, url in links:
            if self.is_valid_link(url, file_path):
                valid_links += 1

        return valid_links / total_links if total_links > 0 else 1.0

    def is_valid_link(self, url: str, file_path: Path) -> bool:
        """Check if a link is valid (simplified validation)."""
        # Skip external URLs (assume valid)
        if url.startswith(("http://", "https://", "mailto:")):
            return True

        # Skip anchors (assume valid)
        if url.startswith("#"):
            return True

        # Check relative file links
        if url.startswith("./") or not url.startswith("/"):
            target_path = file_path.parent / url
        else:
            target_path = self.project_root / url.lstrip("/")

        try:
            return target_path.exists()
        except:
            return False

    def extract_title(self, content: str) -> str:
        """Extract document title from content."""
        lines = content.split("\n")

        # Look for first h1 header
        for line in lines:
            match = re.match(r"^#\s+(.+)$", line)
            if match:
                return match.group(1).strip()

        # Look for title in front matter
        if content.startswith("---"):
            try:
                front_matter_end = content.find("---", 3)
                if front_matter_end != -1:
                    front_matter = content[3:front_matter_end]
                    for line in front_matter.split("\n"):
                        if line.startswith("title:"):
                            return line.split(":", 1)[1].strip().strip("\"'")
            except:
                pass

        return "Untitled Document"

    def calculate_overall_metrics(
        self, documents: list[DocumentAnalysis]
    ) -> dict[str, QualityMetric]:
        """Calculate overall quality metrics across all documents."""
        if not documents:
            return {}

        # Aggregate scores
        readability_scores = [doc.readability_score for doc in documents]
        completeness_scores = [doc.completeness_score for doc in documents]
        consistency_scores = [doc.consistency_score for doc in documents]
        structure_scores = [doc.structure_score for doc in documents]
        link_scores = [doc.link_score for doc in documents]

        # Count totals
        total_words = sum(doc.word_count for doc in documents)
        total_code_examples = sum(doc.code_example_count for doc in documents)
        total_diagrams = sum(doc.diagram_count for doc in documents)
        total_issues = sum(len(doc.issues) for doc in documents)

        metrics = {
            "readability": QualityMetric(
                name="Readability",
                score=statistics.mean(readability_scores),
                weight=1.2,
                details={
                    "average_score": statistics.mean(readability_scores),
                    "best_score": max(readability_scores),
                    "worst_score": min(readability_scores),
                    "distribution": self.score_distribution(readability_scores),
                },
            ),
            "completeness": QualityMetric(
                name="Completeness",
                score=statistics.mean(completeness_scores),
                weight=1.5,
                details={
                    "average_score": statistics.mean(completeness_scores),
                    "incomplete_docs": sum(
                        1 for score in completeness_scores if score < 0.7
                    ),
                },
            ),
            "consistency": QualityMetric(
                name="Consistency",
                score=statistics.mean(consistency_scores),
                weight=1.0,
                details={
                    "average_score": statistics.mean(consistency_scores),
                    "inconsistent_docs": sum(
                        1 for score in consistency_scores if score < 0.8
                    ),
                },
            ),
            "structure": QualityMetric(
                name="Structure",
                score=statistics.mean(structure_scores),
                weight=1.0,
                details={
                    "average_score": statistics.mean(structure_scores),
                    "poorly_structured_docs": sum(
                        1 for score in structure_scores if score < 0.6
                    ),
                },
            ),
            "links": QualityMetric(
                name="Link Quality",
                score=statistics.mean(link_scores),
                weight=0.8,
                details={
                    "average_score": statistics.mean(link_scores),
                    "broken_link_docs": sum(1 for score in link_scores if score < 1.0),
                },
            ),
            "comprehensiveness": QualityMetric(
                name="Comprehensiveness",
                score=self.calculate_comprehensiveness_score(
                    total_words, total_code_examples, total_diagrams, len(documents)
                ),
                weight=1.0,
                details={
                    "total_words": total_words,
                    "total_code_examples": total_code_examples,
                    "total_diagrams": total_diagrams,
                    "documents_count": len(documents),
                },
            ),
            "maintainability": QualityMetric(
                name="Maintainability",
                score=1.0
                - min(
                    1.0, total_issues / (len(documents) * 3)
                ),  # Max 3 issues per doc before score drops
                weight=1.0,
                details={
                    "total_issues": total_issues,
                    "average_issues_per_doc": total_issues / len(documents),
                    "docs_with_issues": sum(1 for doc in documents if doc.issues),
                },
            ),
        }

        return metrics

    def calculate_comprehensiveness_score(
        self, total_words: int, code_examples: int, diagrams: int, doc_count: int
    ) -> float:
        """Calculate comprehensiveness score based on content volume and variety."""
        # Words per document target: 500-1500 words
        avg_words = total_words / doc_count if doc_count > 0 else 0
        words_score = max(0, min(1, avg_words / 1000))  # Normalize to 1000 words

        # Code examples score
        examples_per_doc = code_examples / doc_count if doc_count > 0 else 0
        examples_score = max(
            0, min(1, examples_per_doc / 3)
        )  # Target: 3 examples per doc

        # Diagrams score
        diagrams_per_doc = diagrams / doc_count if doc_count > 0 else 0
        diagrams_score = max(
            0, min(1, diagrams_per_doc / 1)
        )  # Target: 1 diagram per doc

        # Weighted combination
        return words_score * 0.5 + examples_score * 0.3 + diagrams_score * 0.2

    def score_distribution(self, scores: list[float]) -> dict[str, int]:
        """Calculate distribution of scores across quality grades."""
        distribution = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}

        for score in scores:
            if score >= self.thresholds["excellent"]:
                distribution["excellent"] += 1
            elif score >= self.thresholds["good"]:
                distribution["good"] += 1
            elif score >= self.thresholds["fair"]:
                distribution["fair"] += 1
            else:
                distribution["poor"] += 1

        return distribution

    def generate_recommendations(
        self, documents: list[DocumentAnalysis], metrics: dict[str, QualityMetric]
    ) -> list[str]:
        """Generate actionable recommendations for improving documentation quality."""
        recommendations = []

        # Overall score recommendations
        overall_score = statistics.mean([m.score for m in metrics.values()])
        if overall_score < self.thresholds["good"]:
            recommendations.append(
                "📈 Overall documentation quality needs improvement. Focus on the lowest-scoring areas first."
            )

        # Specific metric recommendations
        for metric_name, metric in metrics.items():
            if metric.score < self.thresholds["fair"]:
                if metric_name == "readability":
                    recommendations.append(
                        "📖 Improve readability by shortening sentences, using simpler words, and adding more examples."
                    )
                elif metric_name == "completeness":
                    recommendations.append(
                        "📋 Add missing essential sections. Review document templates for your document types."
                    )
                elif metric_name == "consistency":
                    recommendations.append(
                        "🎯 Establish and follow consistent formatting guidelines for headers, links, and terminology."
                    )
                elif metric_name == "structure":
                    recommendations.append(
                        "🏗️ Improve document structure with clear hierarchical headers and table of contents."
                    )
                elif metric_name == "links":
                    recommendations.append(
                        "🔗 Fix broken links and ensure all internal references are valid."
                    )

        # Document-specific recommendations
        short_docs = [doc for doc in documents if doc.word_count < 200]
        if short_docs:
            recommendations.append(
                f"📝 {len(short_docs)} document(s) are very short. Consider adding more detail and examples."
            )

        docs_without_examples = [
            doc
            for doc in documents
            if doc.code_example_count == 0 and "api" in doc.file_path.lower()
        ]
        if docs_without_examples:
            recommendations.append(
                f"💻 {len(docs_without_examples)} API document(s) lack code examples. Add practical usage examples."
            )

        docs_without_diagrams = [
            doc
            for doc in documents
            if doc.diagram_count == 0 and "architecture" in doc.file_path.lower()
        ]
        if docs_without_diagrams:
            recommendations.append(
                f"📊 {len(docs_without_diagrams)} architecture document(s) lack diagrams. Add visual representations."
            )

        # Maintenance recommendations
        total_issues = sum(len(doc.issues) for doc in documents)
        if total_issues > len(documents):  # More than 1 issue per document on average
            recommendations.append(
                "🔧 High number of quality issues detected. Consider implementing automated quality checks."
            )

        # Positive reinforcement
        if overall_score >= self.thresholds["excellent"]:
            recommendations.append(
                "🎉 Excellent documentation quality! Keep maintaining these high standards."
            )
        elif overall_score >= self.thresholds["good"]:
            recommendations.append(
                "👍 Good documentation quality! Focus on minor improvements to reach excellence."
            )

        return recommendations[:10]  # Limit to top 10 recommendations

    def create_summary(
        self, documents: list[DocumentAnalysis], metrics: dict[str, QualityMetric]
    ) -> dict[str, Any]:
        """Create executive summary of quality assessment."""
        total_words = sum(doc.word_count for doc in documents)
        total_issues = sum(len(doc.issues) for doc in documents)

        return {
            "total_documents": len(documents),
            "total_words": total_words,
            "average_words_per_document": (
                total_words / len(documents) if documents else 0
            ),
            "total_code_examples": sum(doc.code_example_count for doc in documents),
            "total_diagrams": sum(doc.diagram_count for doc in documents),
            "total_issues": total_issues,
            "documents_with_issues": sum(1 for doc in documents if doc.issues),
            "quality_grade": self.get_quality_grade(
                statistics.mean([m.score for m in metrics.values()])
            ),
            "best_document": (
                max(documents, key=lambda d: d.overall_score).file_path
                if documents
                else None
            ),
            "worst_document": (
                min(documents, key=lambda d: d.overall_score).file_path
                if documents
                else None
            ),
            "metric_scores": {
                name: round(metric.score, 3) for name, metric in metrics.items()
            },
        }

    def get_quality_grade(self, score: float) -> str:
        """Convert numeric score to quality grade."""
        if score >= self.thresholds["excellent"]:
            return "Excellent"
        elif score >= self.thresholds["good"]:
            return "Good"
        elif score >= self.thresholds["fair"]:
            return "Fair"
        else:
            return "Poor"

    def export_report(
        self,
        report: QualityReport,
        format_type: str = "json",
        output_path: Path | None = None,
    ) -> None:
        """Export quality report in specified format."""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = (
                self.project_root / f"docs_quality_report_{timestamp}.{format_type}"
            )

        if format_type == "json":
            self._export_json(report, output_path)
        elif format_type == "html":
            self._export_html(report, output_path)
        elif format_type == "text":
            self._export_text(report, output_path)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def _export_json(self, report: QualityReport, output_path: Path) -> None:
        """Export report as JSON."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"📄 JSON report saved to: {output_path}")

    def _export_html(self, report: QualityReport, output_path: Path) -> None:
        """Export report as HTML."""
        html_content = self._generate_html_report(report)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"🌐 HTML report saved to: {output_path}")

    def _export_text(self, report: QualityReport, output_path: Path) -> None:
        """Export report as plain text."""
        text_content = self._generate_text_report(report)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text_content)
        print(f"📝 Text report saved to: {output_path}")

    def _generate_html_report(self, report: QualityReport) -> str:
        """Generate HTML report content."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Documentation Quality Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; }}
        .header h1 {{ margin: 0; font-size: 2.5rem; }}
        .header .subtitle {{ opacity: 0.9; margin-top: 10px; }}
        .content {{ padding: 30px; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }}
        .metric-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff; }}
        .metric-card h3 {{ margin-top: 0; color: #333; }}
        .score {{ font-size: 2rem; font-weight: bold; color: #007bff; }}
        .score-bar {{ width: 100%; height: 8px; background: #e9ecef; border-radius: 4px; overflow: hidden; }}
        .score-fill {{ height: 100%; background: linear-gradient(90deg, #dc3545 0%, #ffc107 50%, #28a745 100%); transition: width 0.3s ease; }}
        .documents-table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .documents-table th, .documents-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        .documents-table th {{ background: #f8f9fa; font-weight: 600; }}
        .grade {{ padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }}
        .grade-excellent {{ background: #d4edda; color: #155724; }}
        .grade-good {{ background: #d1ecf1; color: #0c5460; }}
        .grade-fair {{ background: #fff3cd; color: #856404; }}
        .grade-poor {{ background: #f8d7da; color: #721c24; }}
        .recommendations {{ background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .recommendations ul {{ margin: 0; }}
        .recommendations li {{ margin: 10px 0; }}
        .summary-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-item {{ text-align: center; padding: 15px; background: #f8f9fa; border-radius: 8px; }}
        .stat-number {{ font-size: 1.8rem; font-weight: bold; color: #007bff; }}
        .stat-label {{ color: #6c757d; font-size: 0.9rem; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Documentation Quality Report</h1>
            <div class="subtitle">
                Generated on {datetime.fromisoformat(report.generated_at).strftime('%B %d, %Y at %I:%M %p')}
                | Overall Score: {report.overall_score:.1%} ({self.get_quality_grade(report.overall_score)})
            </div>
        </div>

        <div class="content">
            <section>
                <h2>📈 Quality Metrics</h2>
                <div class="metrics-grid">
                    {self._generate_metric_cards_html(report.metrics)}
                </div>
            </section>

            <section>
                <h2>📋 Summary Statistics</h2>
                <div class="summary-stats">
                    <div class="stat-item">
                        <div class="stat-number">{report.summary['total_documents']}</div>
                        <div class="stat-label">Total Documents</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{report.summary['total_words']:,}</div>
                        <div class="stat-label">Total Words</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{report.summary['total_code_examples']}</div>
                        <div class="stat-label">Code Examples</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{report.summary['total_diagrams']}</div>
                        <div class="stat-label">Diagrams</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-number">{report.summary['total_issues']}</div>
                        <div class="stat-label">Issues Found</div>
                    </div>
                </div>
            </section>

            <section>
                <h2>💡 Recommendations</h2>
                <div class="recommendations">
                    <ul>
                        {''.join(f'<li>{rec}</li>' for rec in report.recommendations)}
                    </ul>
                </div>
            </section>

            <section>
                <h2>📚 Document Analysis</h2>
                <table class="documents-table">
                    <thead>
                        <tr>
                            <th>Document</th>
                            <th>Overall Score</th>
                            <th>Words</th>
                            <th>Code Examples</th>
                            <th>Issues</th>
                            <th>Grade</th>
                        </tr>
                    </thead>
                    <tbody>
                        {self._generate_document_rows_html(report.documents)}
                    </tbody>
                </table>
            </section>
        </div>
    </div>
</body>
</html>
"""

    def _generate_metric_cards_html(self, metrics: dict[str, QualityMetric]) -> str:
        """Generate HTML for metric cards."""
        cards = []
        for name, metric in metrics.items():
            score_percent = metric.percentage
            cards.append(
                f"""
                <div class="metric-card">
                    <h3>{metric.name}</h3>
                    <div class="score">{score_percent:.1f}%</div>
                    <div class="score-bar">
                        <div class="score-fill" style="width: {score_percent}%"></div>
                    </div>
                </div>
            """
            )
        return "".join(cards)

    def _generate_document_rows_html(self, documents: list[DocumentAnalysis]) -> str:
        """Generate HTML table rows for documents."""
        rows = []
        for doc in sorted(documents, key=lambda d: d.overall_score, reverse=True):
            grade = self.get_quality_grade(doc.overall_score).lower()
            rows.append(
                f"""
                <tr>
                    <td>{doc.file_path}</td>
                    <td>{doc.overall_score:.1%}</td>
                    <td>{doc.word_count:,}</td>
                    <td>{doc.code_example_count}</td>
                    <td>{len(doc.issues)}</td>
                    <td><span class="grade grade-{grade}">{grade.title()}</span></td>
                </tr>
            """
            )
        return "".join(rows)

    def _generate_text_report(self, report: QualityReport) -> str:
        """Generate plain text report content."""
        lines = [
            "=" * 60,
            "DOCUMENTATION QUALITY REPORT",
            "=" * 60,
            f"Generated: {report.generated_at}",
            f"Overall Score: {report.overall_score:.1%} ({self.get_quality_grade(report.overall_score)})",
            "",
            "QUALITY METRICS",
            "-" * 20,
        ]

        for name, metric in report.metrics.items():
            lines.append(f"{metric.name}: {metric.percentage:.1f}%")

        lines.extend(
            [
                "",
                "SUMMARY STATISTICS",
                "-" * 20,
                f"Total Documents: {report.summary['total_documents']}",
                f"Total Words: {report.summary['total_words']:,}",
                f"Code Examples: {report.summary['total_code_examples']}",
                f"Diagrams: {report.summary['total_diagrams']}",
                f"Issues Found: {report.summary['total_issues']}",
                "",
                "RECOMMENDATIONS",
                "-" * 20,
            ]
        )

        for rec in report.recommendations:
            lines.append(f"• {rec}")

        lines.extend(["", "DOCUMENT ANALYSIS", "-" * 20])

        for doc in sorted(
            report.documents, key=lambda d: d.overall_score, reverse=True
        ):
            lines.extend(
                [
                    f"{doc.file_path}",
                    f"  Score: {doc.overall_score:.1%} | Words: {doc.word_count:,} | Issues: {len(doc.issues)}",
                    "",
                ]
            )

        return "\n".join(lines)


def main() -> None:
    """Main entry point for documentation quality checker."""
    parser = argparse.ArgumentParser(description="Documentation Quality Checker")
    parser.add_argument(
        "--format",
        choices=["json", "html", "text"],
        default="html",
        help="Output format (default: html)",
    )
    parser.add_argument("--output", help="Output file path")
    parser.add_argument("--project-root", default=".", help="Project root directory")

    args = parser.parse_args()

    try:
        # Initialize checker
        project_root = Path(args.project_root).resolve()
        checker = DocumentationQualityChecker(project_root)

        # Perform analysis
        report = checker.analyze_all_documents()

        # Export report
        output_path = Path(args.output) if args.output else None
        checker.export_report(report, args.format, output_path)

        # Print summary to console
        print("\n📊 Quality Assessment Summary:")
        print(
            f"   Overall Score: {report.overall_score:.1%} ({checker.get_quality_grade(report.overall_score)})"
        )
        print(f"   Documents: {len(report.documents)}")
        print(f"   Total Issues: {report.summary['total_issues']}")

        # Exit with appropriate code
        if report.overall_score >= 0.8:
            exit_code = 0
        elif report.overall_score >= 0.6:
            exit_code = 1
        else:
            exit_code = 2

        exit(exit_code)

    except KeyboardInterrupt:
        print("\n⚠️  Quality check cancelled by user")
        exit(1)
    except Exception as e:
        print(f"❌ Quality check failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
