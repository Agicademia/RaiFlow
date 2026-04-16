"""
Comprehensive Test Suite for EU AI Act Compliance

This module provides pytest tests for validating RaiFlow's EU AI Act
compliance evaluation capabilities across all mapped articles (9-14).
"""

import pytest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from raiflow.engine import ComplianceEngine, DeJureComplianceEngine
from raiflow.evaluators.llm_judge import RaiFlowJudge
from raiflow.evaluators.eu_ai_act import EUAIActEvaluators, create_eu_ai_act_evaluators


# ==================== Fixtures ====================

@pytest.fixture
def eu_policy_path():
    """Path to the EU AI Act policy YAML."""
    return str(Path(__file__).parent.parent / "policies" / "eu_ai_act.yaml")


@pytest.fixture
def judge():
    """Create a judge instance (uses Llama3 by default)."""
    return RaiFlowJudge(model="llama3:latest")


@pytest.fixture
def evaluators(judge):
    """Create EU AI Act evaluators with a judge."""
    return EUAIActEvaluators(judge)


@pytest.fixture
def compliance_engine(eu_policy_path):
    """Create a basic compliance engine."""
    return ComplianceEngine(eu_policy_path)


@pytest.fixture
def dejure_engine(eu_policy_path, judge):
    """Create a De Jure compliance engine."""
    return DeJureComplianceEngine(eu_policy_path, judge, threshold=0.75, max_retries=2)


# ==================== Test Data ====================

class SampleData:
    """Sample data for testing EU AI Act compliance scenarios."""
    
    @staticmethod
    def compliant_risk_management():
        """Sample data for compliant risk management system."""
        return {
            "question": "Does the system have a risk management process?",
            "context": """
            Our AI system implements a comprehensive risk management system as per EU AI Act Article 9.
            The risk management process includes:
            - Systematic risk identification covering the entire lifecycle
            - Risk estimation using likelihood and severity matrices
            - Risk evaluation with documented methodology
            - Risk control measures including technical and organizational safeguards
            - Regular updates and iterative improvements
            - Consideration of impacts on vulnerable groups including minors
            - Documentation of all risk assessments and decisions
            """,
            "answer": "Yes, our system has a fully documented risk management system that covers all lifecycle stages, identifies and evaluates risks, implements control measures, and is regularly updated."
        }
    
    @staticmethod
    def non_compliant_risk_management():
        """Sample data for non-compliant risk management."""
        return {
            "question": "What risk management measures are in place?",
            "context": """
            We have some basic testing procedures.
            """,
            "answer": "We test the system before release."
        }
    
    @staticmethod
    def compliant_data_governance():
        """Sample data for compliant data governance."""
        return {
            "question": "How do you ensure data quality and governance?",
            "context": """
            Our data governance framework for EU AI Act Article 10 compliance includes:
            - Comprehensive data collection protocols with documented origins
            - Rigorous data preparation including annotation, labeling, and cleaning
            - Bias detection using statistical methods across protected characteristics
            - Bias mitigation through re-sampling and algorithmic adjustments
            - Dataset quality assessment for relevance, representativeness, and accuracy
            - Contextual relevance validation for deployment environments
            - Assessment of dataset availability, quantity, and suitability
            - Special safeguards for sensitive data processing
            """,
            "answer": "We implement comprehensive data governance including documented collection processes, rigorous preparation operations, continuous bias detection and mitigation, and regular quality assessments ensuring representativeness and contextual relevance."
        }
    
    @staticmethod
    def non_compliant_data_governance():
        """Sample data for non-compliant data governance."""
        return {
            "question": "What data governance practices do you follow?",
            "context": """
            We use publicly available datasets for training.
            """,
            "answer": "We use standard datasets."
        }
    
    @staticmethod
    def compliant_technical_documentation():
        """Sample data for compliant technical documentation."""
        return {
            "question": "Is technical documentation available?",
            "context": """
            Our technical documentation per EU AI Act Article 11 includes:
            - Complete system description and intended purpose
            - Detailed architecture and design documentation
            - Development process documentation
            - Testing and validation reports
            - Risk management documentation
            - Data governance documentation
            - Performance metrics and accuracy assessments
            - Limitations and known issues
            - Deployment requirements and specifications
            - Maintenance and update procedures
            - Version control and change management
            """,
            "answer": "Yes, comprehensive technical documentation is maintained and updated, covering all required elements including system description, architecture, testing, risk management, and performance metrics."
        }
    
    @staticmethod
    def compliant_logging():
        """Sample data for compliant logging (Article 12)."""
        return {
            "question": "Does the system maintain logs?",
            "context": """
            Our system implements automatic logging as per EU AI Act Article 12:
            - Automatic event recording throughout system lifetime
            - Secure, tamper-resistant log storage
            - Comprehensive traceability including:
              * System inputs and outputs
              * Decision timestamps and reasoning
              * User interactions and overrides
              * System modifications and updates
              * Error conditions and exceptions
            - For biometric systems: usage periods, reference databases, matched inputs, verifying personnel
            - Log retention for minimum 6 months
            - Audit trail for post-market monitoring
            """,
            "answer": "Yes, the system automatically records all relevant events with secure storage, comprehensive traceability, and appropriate retention periods."
        }
    
    @staticmethod
    def non_compliant_logging():
        """Sample data for non-compliant logging."""
        return {
            "question": "What logging capabilities exist?",
            "context": """
            We sometimes save errors to a file.
            """,
            "answer": "We log some errors when they occur."
        }
    
    @staticmethod
    def compliant_transparency():
        """Sample data for compliant transparency (Article 13)."""
        return {
            "question": "How transparent is the system?",
            "context": """
            Our transparency measures per EU AI Act Article 13 include:
            - System designed for interpretable outputs
            - Comprehensive instructions for use including:
              * Provider identity and contact details
              * System capabilities and limitations
              * Performance metrics and accuracy data
              * Known limitations and failure modes
              * Human oversight measures
              * Computational requirements
              * Log interpretation guidelines
            - Output explanation capabilities
            - Clear presentation of confidence scores
            - Documentation of decision factors
            """,
            "answer": "The system provides transparent operation with comprehensive instructions, interpretable outputs, and clear documentation of capabilities and limitations."
        }
    
    @staticmethod
    def compliant_human_oversight():
        """Sample data for compliant human oversight (Article 14)."""
        return {
            "question": "How is human oversight implemented?",
            "context": """
            Our human oversight measures per EU AI Act Article 14 include:
            - Human-machine interface tools for effective monitoring
            - Real-time system status display
            - Clear indication of system confidence levels
            - Override mechanisms accessible to operators
            - Emergency stop functionality
            - Training materials for operators
            - Documentation of oversight procedures
            - Measures to prevent automation bias
            - Capability for human intervention at any stage
            - Audit trail of human interventions
            """,
            "answer": "Comprehensive human oversight is implemented through intuitive interfaces, clear status indicators, accessible override mechanisms, and thorough operator training."
        }
    
    @staticmethod
    def non_compliant_oversight():
        """Sample data for non-compliant human oversight."""
        return {
            "question": "Can humans intervene in the system?",
            "context": """
            The system runs automatically.
            """,
            "answer": "Humans can turn it off if needed."
        }


# ==================== Policy Loading Tests ====================

class TestPolicyLoading:
    """Tests for EU AI Act policy loading and structure."""
    
    def test_policy_file_exists(self, eu_policy_path):
        """Verify the EU AI Act policy file exists."""
        assert os.path.exists(eu_policy_path), "EU AI Act policy file not found"
    
    def test_policy_loads_valid_yaml(self, eu_policy_path):
        """Verify the policy file is valid YAML."""
        import yaml
        with open(eu_policy_path, 'r') as f:
            policy = yaml.safe_load(f)
        assert policy is not None, "Policy YAML is empty"
        assert "policy_name" in policy, "Missing policy_name"
        assert "regulatory_sections" in policy, "Missing regulatory_sections"
    
    def test_policy_covers_required_articles(self, eu_policy_path):
        """Verify policy covers Articles 9-14."""
        import yaml
        with open(eu_policy_path, 'r') as f:
            policy = yaml.safe_load(f)
        
        section_ids = [section['section_id'] for section in policy['regulatory_sections']]
        required_articles = ['Article 9', 'Article 10', 'Article 11', 'Article 12', 'Article 13', 'Article 14']
        
        for article in required_articles:
            assert article in section_ids, f"Missing {article} in policy"
    
    def test_policy_has_rules_for_each_article(self, eu_policy_path):
        """Verify each article has at least one rule."""
        import yaml
        with open(eu_policy_path, 'r') as f:
            policy = yaml.safe_load(f)
        
        for section in policy['regulatory_sections']:
            assert 'rules' in section, f"Section {section['section_id']} has no rules"
            assert len(section['rules']) > 0, f"Section {section['section_id']} has empty rules"


# ==================== Evaluator Tests ====================

class TestEUAIEvaluators:
    """Tests for EU AI Act evaluators."""
    
    def test_evaluators_initialization(self, evaluators):
        """Verify evaluators can be initialized."""
        assert evaluators is not None
        assert hasattr(evaluators, 'judge')
    
    def test_all_evaluators_available(self, evaluators):
        """Verify all required evaluators are available."""
        all_evaluators = evaluators.get_all_evaluators()
        
        # Article 9 evaluators
        assert 'risk_management_system_check' in all_evaluators
        assert 'risk_identification_check' in all_evaluators
        assert 'risk_evaluation_check' in all_evaluators
        assert 'risk_control_check' in all_evaluators
        assert 'vulnerable_groups_check' in all_evaluators
        assert 'iterative_risk_management_check' in all_evaluators
        
        # Article 10 evaluators
        assert 'data_governance_check' in all_evaluators
        assert 'dataset_quality_check' in all_evaluators
        assert 'bias_detection_check' in all_evaluators
        assert 'data_preparation_check' in all_evaluators
        assert 'dataset_assessment_check' in all_evaluators
        assert 'contextual_relevance_check' in all_evaluators
        
        # Article 11 evaluators
        assert 'technical_documentation_check' in all_evaluators
        assert 'documentation_maintenance_check' in all_evaluators
        assert 'compliance_demonstration_check' in all_evaluators
        
        # Article 12 evaluators
        assert 'automatic_logging_check' in all_evaluators
        assert 'traceability_logging_check' in all_evaluators
        assert 'biometric_logging_check' in all_evaluators
        
        # Article 13 evaluators
        assert 'transparency_by_design_check' in all_evaluators
        assert 'instructions_provision_check' in all_evaluators
        assert 'instructions_content_check' in all_evaluators
        assert 'output_interpretability_check' in all_evaluators
        
        # Article 14 evaluators
        assert 'human_oversight_design_check' in all_evaluators
        assert 'risk_prevention_oversight_check' in all_evaluators
        assert 'oversight_measures_check' in all_evaluators
        assert 'human_understanding_check' in all_evaluators
        assert 'intervention_capability_check' in all_evaluators
    
    def test_score_extraction(self, evaluators):
        """Test score extraction from various response formats."""
        # Test JSON format
        assert 0.0 <= evaluators._extract_score('{"score": 0.85}') <= 1.0
        assert 0.0 <= evaluators._extract_score('{"score": 0.0}') <= 1.0
        assert 0.0 <= evaluators._extract_score('{"score": 1.0}') <= 1.0
        
        # Test text format with score
        assert 0.0 <= evaluators._extract_score('Score: 0.75') <= 1.0
        assert 0.0 <= evaluators._extract_score('The score is 0.9') <= 1.0
        
        # Test fallback
        assert evaluators._extract_score('invalid response') == 0.5


# ==================== Compliance Scenario Tests ====================

class TestComplianceScenarios:
    """Tests for various EU AI Act compliance scenarios."""
    
    def test_compliant_risk_management(self, evaluators):
        """Test that compliant risk management scores high."""
        data = SampleData.compliant_risk_management()
        score = evaluators.risk_management_system_check(data)
        assert score >= 0.5, f"Compliant risk management scored too low: {score}"
    
    def test_non_compliant_risk_management(self, evaluators):
        """Test that non-compliant risk management scores low."""
        data = SampleData.non_compliant_risk_management()
        score = evaluators.risk_management_system_check(data)
        assert score <= 0.5, f"Non-compliant risk management scored too high: {score}"
    
    def test_compliant_data_governance(self, evaluators):
        """Test that compliant data governance scores high."""
        data = SampleData.compliant_data_governance()
        score = evaluators.data_governance_check(data)
        assert score >= 0.5, f"Compliant data governance scored too low: {score}"
    
    def test_non_compliant_data_governance(self, evaluators):
        """Test that non-compliant data governance scores low."""
        data = SampleData.non_compliant_data_governance()
        score = evaluators.data_governance_check(data)
        assert score <= 0.5, f"Non-compliant data governance scored too high: {score}"
    
    def test_compliant_technical_documentation(self, evaluators):
        """Test that compliant technical documentation scores high."""
        data = SampleData.compliant_technical_documentation()
        score = evaluators.technical_documentation_check(data)
        assert score >= 0.7, f"Compliant documentation scored too low: {score}"
    
    def test_compliant_logging(self, evaluators):
        """Test that compliant logging scores high."""
        data = SampleData.compliant_logging()
        score = evaluators.automatic_logging_check(data)
        assert score >= 0.7, f"Compliant logging scored too low: {score}"
    
    def test_non_compliant_logging(self, evaluators):
        """Test that non-compliant logging scores low."""
        data = SampleData.non_compliant_logging()
        score = evaluators.automatic_logging_check(data)
        assert score <= 0.7, f"Non-compliant logging scored too high: {score}"
    
    def test_compliant_transparency(self, evaluators):
        """Test that compliant transparency scores high."""
        data = SampleData.compliant_transparency()
        score = evaluators.transparency_by_design_check(data)
        assert score >= 0.7, f"Compliant transparency scored too low: {score}"
    
    def test_compliant_human_oversight(self, evaluators):
        """Test that compliant human oversight scores high."""
        data = SampleData.compliant_human_oversight()
        score = evaluators.human_oversight_design_check(data)
        assert score >= 0.5, f"Compliant oversight scored too low: {score}"
    
    def test_non_compliant_oversight(self, evaluators):
        """Test that non-compliant oversight scores low."""
        data = SampleData.non_compliant_oversight()
        score = evaluators.human_oversight_design_check(data)
        assert score <= 0.5, f"Non-compliant oversight scored too high: {score}"


# ==================== Engine Integration Tests ====================

class TestEngineIntegration:
    """Tests for compliance engine integration."""
    
    def test_compliance_engine_loads_policy(self, compliance_engine):
        """Verify compliance engine loads the EU AI Act policy."""
        assert compliance_engine.policy is not None
        assert compliance_engine.policy['policy_name'] == "EU Artificial Intelligence Act"
    
    def test_dejure_engine_loads_policy(self, dejure_engine):
        """Verify De Jure engine loads the EU AI Act policy."""
        assert dejure_engine.policy is not None
        assert dejure_engine.policy['policy_name'] == "EU Artificial Intelligence Act"
    
    def test_dejure_engine_runs_audit(self, dejure_engine):
        """Verify De Jure engine can run an audit on sample text."""
        sample_text = """
        Our AI system implements comprehensive risk management, data governance,
        technical documentation, automatic logging, transparency measures, and
        human oversight as required by the EU AI Act.
        """
        result = dejure_engine.run_compliance_audit(sample_text, section_id="Article 9")
        assert result is not None
        assert 'sections' in result
        assert len(result['sections']) > 0
    
    def test_score_bounds(self, evaluators):
        """Verify all evaluator scores are within valid bounds [0.0, 1.0]."""
        test_data = {
            "question": "Test question",
            "context": "Test context with some information",
            "answer": "Test answer based on context"
        }
        
        all_evaluators = evaluators.get_all_evaluators()
        for name, evaluator_func in all_evaluators.items():
            try:
                score = evaluator_func(test_data)
                assert 0.0 <= score <= 1.0, f"{name} returned out-of-bounds score: {score}"
            except Exception as e:
                pytest.fail(f"Evaluator {name} raised exception: {e}")


# ==================== Article-Specific Tests ====================

class TestArticle9RiskManagement:
    """Tests specifically for Article 9 - Risk Management."""
    
    def test_all_article9_evaluators_exist(self, evaluators):
        """Verify all Article 9 evaluators exist."""
        all_evals = evaluators.get_all_evaluators()
        article9_evals = [
            'risk_management_system_check',
            'risk_identification_check',
            'risk_evaluation_check',
            'risk_control_check',
            'vulnerable_groups_check',
            'iterative_risk_management_check'
        ]
        for eval_name in article9_evals:
            assert eval_name in all_evals, f"Missing Article 9 evaluator: {eval_name}"


class TestArticle10DataGovernance:
    """Tests specifically for Article 10 - Data Governance."""
    
    def test_all_article10_evaluators_exist(self, evaluators):
        """Verify all Article 10 evaluators exist."""
        all_evals = evaluators.get_all_evaluators()
        article10_evals = [
            'data_governance_check',
            'dataset_quality_check',
            'bias_detection_check',
            'data_preparation_check',
            'dataset_assessment_check',
            'contextual_relevance_check'
        ]
        for eval_name in article10_evals:
            assert eval_name in all_evals, f"Missing Article 10 evaluator: {eval_name}"


class TestArticle11TechnicalDocumentation:
    """Tests specifically for Article 11 - Technical Documentation."""
    
    def test_all_article11_evaluators_exist(self, evaluators):
        """Verify all Article 11 evaluators exist."""
        all_evals = evaluators.get_all_evaluators()
        article11_evals = [
            'technical_documentation_check',
            'documentation_maintenance_check',
            'compliance_demonstration_check'
        ]
        for eval_name in article11_evals:
            assert eval_name in all_evals, f"Missing Article 11 evaluator: {eval_name}"


class TestArticle12RecordKeeping:
    """Tests specifically for Article 12 - Record Keeping."""
    
    def test_all_article12_evaluators_exist(self, evaluators):
        """Verify all Article 12 evaluators exist."""
        all_evals = evaluators.get_all_evaluators()
        article12_evals = [
            'automatic_logging_check',
            'traceability_logging_check',
            'biometric_logging_check'
        ]
        for eval_name in article12_evals:
            assert eval_name in all_evals, f"Missing Article 12 evaluator: {eval_name}"


class TestArticle13Transparency:
    """Tests specifically for Article 13 - Transparency."""
    
    def test_all_article13_evaluators_exist(self, evaluators):
        """Verify all Article 13 evaluators exist."""
        all_evals = evaluators.get_all_evaluators()
        article13_evals = [
            'transparency_by_design_check',
            'instructions_provision_check',
            'instructions_content_check',
            'output_interpretability_check'
        ]
        for eval_name in article13_evals:
            assert eval_name in all_evals, f"Missing Article 13 evaluator: {eval_name}"


class TestArticle14HumanOversight:
    """Tests specifically for Article 14 - Human Oversight."""
    
    def test_all_article14_evaluators_exist(self, evaluators):
        """Verify all Article 14 evaluators exist."""
        all_evals = evaluators.get_all_evaluators()
        article14_evals = [
            'human_oversight_design_check',
            'risk_prevention_oversight_check',
            'oversight_measures_check',
            'human_understanding_check',
            'intervention_capability_check'
        ]
        for eval_name in article14_evals:
            assert eval_name in all_evals, f"Missing Article 14 evaluator: {eval_name}"


# ==================== End-to-End Tests ====================

class TestEndToEnd:
    """End-to-end tests for complete compliance workflows."""
    
    def test_full_audit_workflow(self, dejure_engine):
        """Test running a complete audit across all sections."""
        sample_text = """
        Our high-risk AI system is developed with comprehensive compliance measures:
        - Risk management system covering all lifecycle stages
        - Data governance with bias detection and mitigation
        - Complete technical documentation
        - Automatic logging with traceability
        - Transparent operation with clear instructions
        - Human oversight with intervention capabilities
        """
        
        results = dejure_engine.run_compliance_audit(sample_text)
        assert results is not None
        assert 'sections' in results
        # Should have results for all sections
        assert len(results['sections']) >= 6  # Articles 9-14
    
    def test_shield_decorator_integration(self):
        """Test that shield decorator works with EU AI Act policy."""
        from raiflow import shield
        
        @shield(policy="eu_ai_act")
        def test_rag_function(query: str):
            return {
                "answer": "Test answer",
                "context": "Test context with relevant information"
            }
        
        result = test_rag_function("Test query")
        assert result is not None
        assert "answer" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])