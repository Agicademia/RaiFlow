#!/usr/bin/env python3
"""
Project Analyzer for AI Compliance Assessment

This module provides automated analysis of AI projects to extract
compliance-relevant information for regulatory framework evaluation.
"""

import os
import re
import json
import ast
import importlib.util
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class ProjectInfo:
    """Information about an analyzed AI project."""
    name: str
    description: str
    project_type: str  # rag, llm, ml, etc.
    frameworks_used: List[str]
    dependencies: List[str]
    has_rag: bool
    has_llm: bool
    has_vector_db: bool
    has_data_processing: bool
    compliance_risks: List[str]
    code_files: List[str]
    documentation_files: List[str]
    analysis_summary: str


class ProjectAnalyzer:
    """Analyzes AI projects for compliance assessment."""
    
    def __init__(self):
        self.rag_patterns = [
            r'vector_store', r'embedding', r'retriever', r'rag', r'retrieval',
            r'chroma', r'pinecone', r'weaviate', r'milvus', r'faiss',
            r'langchain', r'llama_index', r'haystack', r'vectorsearch',
            r'similarity_search', r'context_retrieval', r'document_store'
        ]
        
        self.llm_patterns = [
            r'openai', r'gpt', r'claude', r'llama', r'mistral', r'gemini',
            r'language_model', r'llm', r'chatgpt', r'api_key', r'model_',
            r'generate', r'completion', r'prompt', r'token', r'inference'
        ]
        
        self.data_patterns = [
            r'pandas', r'numpy', r'dataframe', r'dataset', r'training',
            r'preprocess', r'feature', r'label', r'annotation', r'bias',
            r'fairness', r'privacy', r'pii', r'anonymize', r'encrypt'
        ]
    
    def analyze_directory(self, project_path: str) -> ProjectInfo:
        """Analyze a project directory for AI compliance assessment."""
        project_path = Path(project_path)
        
        if not project_path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")
        
        # Gather project information
        name = project_path.name or "Unknown Project"
        description = self._extract_description(project_path)
        project_type = self._determine_project_type(project_path)
        frameworks = self._extract_frameworks(project_path)
        dependencies = self._extract_dependencies(project_path)
        
        # Analyze code patterns
        code_files = self._find_code_files(project_path)
        has_rag, rag_evidence = self._check_rag_patterns(project_path, code_files)
        has_llm, llm_evidence = self._check_llm_patterns(project_path, code_files)
        has_vector_db = self._check_vector_db(project_path, code_files)
        has_data_processing = self._check_data_processing(project_path, code_files)
        
        # Identify compliance risks
        compliance_risks = self._identify_compliance_risks(
            has_rag, has_llm, has_vector_db, has_data_processing, rag_evidence, llm_evidence
        )
        
        # Find documentation
        doc_files = self._find_documentation(project_path)
        
        # Generate analysis summary
        analysis_summary = self._generate_summary(
            name, project_type, has_rag, has_llm, has_vector_db, 
            has_data_processing, compliance_risks
        )
        
        return ProjectInfo(
            name=name,
            description=description,
            project_type=project_type,
            frameworks_used=frameworks,
            dependencies=dependencies,
            has_rag=has_rag,
            has_llm=has_llm,
            has_vector_db=has_vector_db,
            has_data_processing=has_data_processing,
            compliance_risks=compliance_risks,
            code_files=code_files,
            documentation_files=doc_files,
            analysis_summary=analysis_summary
        )
    
    def analyze_single_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze a single file for compliance-relevant content."""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise ValueError(f"File does not exist: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        analysis = {
            "file_path": str(file_path),
            "file_type": file_path.suffix,
            "has_rag_patterns": self._find_patterns(content, self.rag_patterns),
            "has_llm_patterns": self._find_patterns(content, self.llm_patterns),
            "has_data_patterns": self._find_patterns(content, self.data_patterns),
            "has_pii_handling": self._check_pii_handling(content),
            "has_bias_mitigation": self._check_bias_mitigation(content),
            "has_transparency": self._check_transparency(content),
            "has_documentation": self._check_documentation(content),
        }
        
        return analysis
    
    def _extract_description(self, project_path: Path) -> str:
        """Extract project description from README or setup files."""
        readme_files = ['README.md', 'README.txt', 'README.rst']
        
        for readme in readme_files:
            readme_path = project_path / readme
            if readme_path.exists():
                with open(readme_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                # Extract first paragraph or first 200 characters
                lines = content.split('\n')
                for line in lines:
                    if line.strip() and not line.startswith('#'):
                        return line.strip()[:200]
        
        # Check setup.py or pyproject.toml
        setup_path = project_path / 'setup.py'
        if setup_path.exists():
            try:
                with open(setup_path, 'r') as f:
                    content = f.read()
                match = re.search(r'description=["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)[:200]
            except:
                pass
        
        return "AI Project - No description found"
    
    def _determine_project_type(self, project_path: Path) -> str:
        """Determine the type of AI project."""
        code_files = self._find_code_files(project_path)
        
        # Check for RAG indicators
        has_rag = self._check_rag_patterns(project_path, code_files)[0]
        has_llm = self._check_llm_patterns(project_path, code_files)[0]
        
        if has_rag and has_llm:
            return "rag_system"
        elif has_llm:
            return "llm_application"
        elif has_rag:
            return "retrieval_system"
        else:
            return "ai_application"
    
    def _extract_frameworks(self, project_path: Path) -> List[str]:
        """Extract AI/ML frameworks used in the project."""
        frameworks = set()
        
        # Check requirements.txt
        req_file = project_path / 'requirements.txt'
        if req_file.exists():
            with open(req_file, 'r') as f:
                for line in f:
                    line = line.strip().lower()
                    if 'langchain' in line:
                        frameworks.add('langchain')
                    elif 'llama' in line:
                        frameworks.add('llama_index')
                    elif 'haystack' in line:
                        frameworks.add('haystack')
                    elif 'transformers' in line:
                        frameworks.add('transformers')
                    elif 'torch' in line or 'tensorflow' in line:
                        frameworks.add('pytorch_tensorflow')
        
        # Check imports in Python files
        for py_file in project_path.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                if 'import langchain' in content or 'from langchain' in content:
                    frameworks.add('langchain')
                if 'import llama_index' in content or 'from llama_index' in content:
                    frameworks.add('llama_index')
                if 'import haystack' in content or 'from haystack' in content:
                    frameworks.add('haystack')
            except:
                pass
        
        return list(frameworks)
    
    def _extract_dependencies(self, project_path: Path) -> List[str]:
        """Extract project dependencies."""
        dependencies = []
        
        req_file = project_path / 'requirements.txt'
        if req_file.exists():
            with open(req_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        dependencies.append(line.split('==')[0])
        
        return dependencies[:20]  # Limit to top 20
    
    def _find_code_files(self, project_path: Path) -> List[str]:
        """Find all code files in the project."""
        code_files = []
        for ext in ['*.py', '*.js', '*.ts', '*.java', '*.go', '*.rs']:
            code_files.extend([str(f) for f in project_path.rglob(ext)])
        return code_files[:50]  # Limit to 50 files
    
    def _check_rag_patterns(self, project_path: Path, code_files: List[str]) -> Tuple[bool, List[str]]:
        """Check for RAG-related patterns in the project."""
        evidence = []
        
        for file_path in code_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern in self.rag_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        evidence.append(f"{Path(file_path).name}: {pattern}")
            except:
                pass
        
        return len(evidence) > 0, evidence[:10]
    
    def _check_llm_patterns(self, project_path: Path, code_files: List[str]) -> Tuple[bool, List[str]]:
        """Check for LLM-related patterns in the project."""
        evidence = []
        
        for file_path in code_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern in self.llm_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        evidence.append(f"{Path(file_path).name}: {pattern}")
            except:
                pass
        
        return len(evidence) > 0, evidence[:10]
    
    def _check_vector_db(self, project_path: Path, code_files: List[str]) -> bool:
        """Check for vector database usage."""
        vector_db_patterns = ['chroma', 'pinecone', 'weaviate', 'milvus', 'faiss', 'qdrant']
        
        for file_path in code_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern in vector_db_patterns:
                    if pattern in content.lower():
                        return True
            except:
                pass
        
        return False
    
    def _check_data_processing(self, project_path: Path, code_files: List[str]) -> bool:
        """Check for data processing activities."""
        for file_path in code_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern in self.data_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        return True
            except:
                pass
        
        return False
    
    def _identify_compliance_risks(self, has_rag: bool, has_llm: bool, 
                                  has_vector_db: bool, has_data_processing: bool,
                                  rag_evidence: List[str], llm_evidence: List[str]) -> List[str]:
        """Identify potential compliance risks based on project analysis."""
        risks = []
        
        if has_rag:
            risks.append("RAG system - Requires transparency and grounding checks")
            risks.append("Document retrieval - Must ensure data quality and relevance")
        
        if has_llm:
            risks.append("LLM usage - Requires transparency about AI-generated content")
            risks.append("Potential for hallucinations - Requires fact-checking mechanisms")
        
        if has_vector_db:
            risks.append("Vector database - Must ensure data privacy and security")
            risks.append("Embedding storage - May contain sensitive information")
        
        if has_data_processing:
            risks.append("Data processing - Must comply with data protection regulations")
            risks.append("Potential bias in training data - Requires fairness assessment")
        
        return risks
    
    def _find_documentation(self, project_path: Path) -> List[str]:
        """Find documentation files in the project."""
        doc_files = []
        doc_extensions = ['.md', '.txt', '.rst', '.pdf', '.docx']
        
        for ext in doc_extensions:
            doc_files.extend([str(f) for f in project_path.rglob(f'*{ext}')])
        
        return doc_files[:20]  # Limit to 20 files
    
    def _generate_summary(self, name: str, project_type: str, has_rag: bool, 
                         has_llm: bool, has_vector_db: bool, 
                         has_data_processing: bool, risks: List[str]) -> str:
        """Generate a summary of the project analysis."""
        summary_parts = [f"Project '{name}' is a {project_type.replace('_', ' ')}."]
        
        if has_rag:
            summary_parts.append("Uses RAG (Retrieval-Augmented Generation) architecture.")
        if has_llm:
            summary_parts.append("Integrates with Large Language Models.")
        if has_vector_db:
            summary_parts.append("Utilizes vector database for similarity search.")
        if has_data_processing:
            summary_parts.append("Performs data processing operations.")
        
        summary_parts.append(f"Identified {len(risks)} compliance risk(s) that require attention.")
        
        return " ".join(summary_parts)
    
    def _find_patterns(self, content: str, patterns: List[str]) -> List[str]:
        """Find matching patterns in content."""
        matches = []
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                matches.append(pattern)
        return matches
    
    def _check_pii_handling(self, content: str) -> bool:
        """Check if the code handles PII appropriately."""
        pii_patterns = ['pii', 'personal_data', 'sensitive', 'anonymize', 'redact', 'encrypt']
        return any(pattern in content.lower() for pattern in pii_patterns)
    
    def _check_bias_mitigation(self, content: str) -> bool:
        """Check if the code includes bias mitigation."""
        bias_patterns = ['bias', 'fairness', 'debias', 'fair', 'discrimination', 'equity']
        return any(pattern in content.lower() for pattern in bias_patterns)
    
    def _check_transparency(self, content: str) -> bool:
        """Check if the code includes transparency measures."""
        transparency_patterns = ['explain', 'interpret', 'transparent', 'audit', 'log', 'trace']
        return any(pattern in content.lower() for pattern in transparency_patterns)
    
    def _check_documentation(self, content: str) -> bool:
        """Check if the code is well-documented."""
        # Simple heuristic: check for docstrings and comments
        has_docstrings = '"""' in content or "'''" in content
        has_comments = '#' in content or '//' in content
        return has_docstrings or has_comments


def analyze_project(project_path: str) -> Dict[str, Any]:
    """Convenience function to analyze a project."""
    analyzer = ProjectAnalyzer()
    project_info = analyzer.analyze_directory(project_path)
    return asdict(project_info)