"""
Academic PDF Test Fixtures Generator
Creates realistic academic paper fixtures for RAG testing with citations, references,
and structured content typical of research papers.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # PyMuPDF


class AcademicPDFGenerator:
    """
    Generates academic paper-style PDF test fixtures for realistic RAG testing.
    Features:
    - Research paper structure (abstract, introduction, methods, results, conclusion)
    - Citations and references sections
    - Realistic academic content for citation extraction testing
    - Multi-column layouts where appropriate
    """

    def __init__(self, fixture_dir: Optional[Path] = None):
        """Initialize academic PDF fixture generator."""
        if fixture_dir is None:
            self.fixture_dir = Path(__file__).parent / "pdfs" / "academic"
        else:
            self.fixture_dir = Path(fixture_dir)
        self.fixture_dir.mkdir(parents=True, exist_ok=True)
        self.fixtures: Dict[str, Path] = {}

    def create_ai_research_paper(self, filename: str = "ai_research_sample.pdf") -> Path:
        """Create a sample AI research paper with citations."""
        pdf_path = self.fixture_dir / filename
        doc = fitz.open()

        # Page 1: Title, Abstract, Introduction
        page1 = doc.new_page()

        title = "Deep Learning Approaches for Natural Language Processing: A Comprehensive Review"
        abstract = """Abstract

Natural language processing (NLP) has experienced remarkable advances with the introduction of deep learning techniques. This paper provides a comprehensive review of recent developments in deep learning for NLP, covering transformer architectures, attention mechanisms, and pre-trained language models. We analyze the performance improvements achieved through models like BERT, GPT, and T5, discussing their applications in tasks such as sentiment analysis, machine translation, and question answering. Our findings suggest that transformer-based models have revolutionized the field, achieving state-of-the-art results across multiple benchmarks.

Keywords: natural language processing, deep learning, transformers, BERT, GPT, attention mechanism"""

        introduction = """1. Introduction

The field of natural language processing has undergone a paradigm shift with the advent of deep learning techniques (Devlin et al., 2018). Traditional statistical methods have been largely superseded by neural architectures that can capture complex linguistic patterns and semantic relationships (Vaswani et al., 2017).

Recent advances in transformer architecture have enabled the development of large-scale pre-trained models that demonstrate remarkable performance across diverse NLP tasks (Brown et al., 2020). These models leverage attention mechanisms to process sequential data more effectively than previous recurrent neural network approaches (Bahdanau et al., 2015)."""

        # Add content to page 1
        y_pos = 50
        page1.insert_text((50, y_pos), title, fontsize=16, color=(0, 0, 0))
        y_pos += 60
        page1.insert_text((50, y_pos), abstract, fontsize=10, color=(0, 0, 0))
        y_pos += 200
        page1.insert_text((50, y_pos), introduction, fontsize=11, color=(0, 0, 0))

        # Page 2: Methods and Results
        page2 = doc.new_page()

        methods = """2. Methodology

Our analysis encompasses a systematic review of transformer-based architectures published between 2017 and 2023. We evaluate models based on their performance on standard benchmarks including GLUE (Wang et al., 2018), SuperGLUE (Wang et al., 2019), and SQuAD (Rajpurkar et al., 2016).

2.1 Model Architectures
We examine several key architectures:
- BERT: Bidirectional Encoder Representations from Transformers (Devlin et al., 2018)
- GPT series: Generative Pre-trained Transformers (Radford et al., 2019; Brown et al., 2020)
- T5: Text-to-Text Transfer Transformer (Raffel et al., 2019)
- RoBERTa: Robustly Optimized BERT Pretraining Approach (Liu et al., 2019)"""

        results = """3. Results and Discussion

Our analysis reveals significant performance improvements across all evaluated tasks. BERT achieved an average improvement of 15% over previous state-of-the-art models on GLUE benchmark tasks. GPT-3, with its 175 billion parameters, demonstrated remarkable few-shot learning capabilities (Brown et al., 2020).

The attention mechanism proves crucial for handling long-range dependencies in text, addressing limitations of recurrent architectures (Vaswani et al., 2017). Fine-tuning strategies significantly impact downstream task performance, with task-specific adaptations yielding the best results."""

        page2.insert_text((50, 50), methods, fontsize=11, color=(0, 0, 0))
        page2.insert_text((50, 300), results, fontsize=11, color=(0, 0, 0))

        # Page 3: Conclusion and References
        page3 = doc.new_page()

        conclusion = """4. Conclusion

This comprehensive review demonstrates the transformative impact of deep learning on natural language processing. Transformer-based architectures have established new performance benchmarks across diverse NLP tasks, fundamentally changing how we approach language understanding and generation.

Future research directions include developing more efficient architectures, improving multilingual capabilities, and addressing ethical considerations in large language models. The continued evolution of these technologies promises further advances in human-computer interaction and automated text processing."""

        references = """References

Bahdanau, D., Cho, K., & Bengio, Y. (2015). Neural machine translation by jointly learning to align and translate. International Conference on Learning Representations.

Brown, T. B., Mann, B., Ryder, N., Subbiah, M., Kaplan, J., Dhariwal, P., ... & Amodei, D. (2020). Language models are few-shot learners. Advances in Neural Information Processing Systems, 33, 1877-1901.

Devlin, J., Chang, M. W., Lee, K., & Toutanova, K. (2018). BERT: Pre-training of deep bidirectional transformers for language understanding. arXiv preprint arXiv:1810.04805.

Liu, Y., Ott, M., Goyal, N., Du, J., Joshi, M., Chen, D., ... & Stoyanov, V. (2019). RoBERTa: A robustly optimized BERT pretraining approach. arXiv preprint arXiv:1907.11692.

Radford, A., Wu, J., Child, R., Luan, D., Amodei, D., & Sutskever, I. (2019). Language models are unsupervised multitask learners. OpenAI blog.

Raffel, C., Shazeer, N., Roberts, A., Lee, K., Narang, S., Matena, M., ... & Liu, P. J. (2019). Exploring the limits of transfer learning with a unified text-to-text transformer. arXiv preprint arXiv:1910.10683.

Rajpurkar, P., Zhang, J., Lopyrev, K., & Liang, P. (2016). SQuAD: 100,000+ questions for machine comprehension of text. arXiv preprint arXiv:1606.05250.

Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., ... & Polosukhin, I. (2017). Attention is all you need. Advances in Neural Information Processing Systems, 30.

Wang, A., Singh, A., Michael, J., Hill, F., Levy, O., & Bowman, S. R. (2018). GLUE: A multi-task benchmark and analysis platform for natural language understanding. arXiv preprint arXiv:1804.07461.

Wang, A., Pruksachatkun, Y., Nangia, N., Singh, A., Michael, J., Hill, F., ... & Bowman, S. R. (2019). SuperGLUE: A stickier benchmark for general-purpose language understanding systems. arXiv preprint arXiv:1905.00537."""

        page3.insert_text((50, 50), conclusion, fontsize=11, color=(0, 0, 0))
        page3.insert_text((50, 200), references, fontsize=9, color=(0, 0, 0))

        doc.save(str(pdf_path))
        doc.close()
        self.fixtures[filename] = pdf_path
        return pdf_path

    def create_computer_vision_paper(self, filename: str = "cv_research_sample.pdf") -> Path:
        """Create a sample computer vision research paper."""
        pdf_path = self.fixture_dir / filename
        doc = fitz.open()

        # Page 1: Title and Abstract
        page1 = doc.new_page()

        title = "Convolutional Neural Networks for Image Classification: Recent Advances and Applications"

        content = f"""{title}

Abstract

Computer vision has been revolutionized by deep convolutional neural networks (CNNs). This paper surveys recent developments in CNN architectures for image classification, including ResNet, DenseNet, and EfficientNet. We analyze their performance on ImageNet and discuss practical applications in medical imaging, autonomous vehicles, and security systems.

1. Introduction

Convolutional Neural Networks have transformed computer vision since AlexNet's breakthrough performance on ImageNet (Krizhevsky et al., 2012). Subsequent architectures like VGG (Simonyan & Zisserman, 2014), ResNet (He et al., 2016), and more recent EfficientNet (Tan & Le, 2019) have pushed the boundaries of image recognition accuracy.

The key innovations include deeper networks, skip connections, and architectural search techniques. These developments have enabled applications ranging from medical diagnosis to autonomous navigation (LeCun et al., 2015).

2. Related Work

Early CNN architectures focused on increasing depth and width (Simonyan & Zisserman, 2014). ResNet introduced skip connections to address vanishing gradient problems (He et al., 2016). DenseNet proposed dense connections for better feature reuse (Huang et al., 2017).

Recent work on neural architecture search has automated the design process, leading to more efficient architectures like EfficientNet (Tan & Le, 2019; Real et al., 2019)."""

        page1.insert_text((50, 50), content, fontsize=10, color=(0, 0, 0))

        # Page 2: Results and References
        page2 = doc.new_page()

        results_and_refs = """3. Experimental Results

Our experiments on ImageNet-1K demonstrate significant improvements in accuracy and efficiency. EfficientNet-B7 achieves 84.3% top-1 accuracy while being 8.4x smaller than the best existing ConvNet (Tan & Le, 2019).

4. Applications

Medical Imaging: CNNs have shown remarkable success in medical image analysis, achieving radiologist-level performance in skin cancer detection (Esteva et al., 2017).

Autonomous Vehicles: Real-time object detection and segmentation enable safe navigation in complex environments (Chen et al., 2015).

References

Chen, X., Ma, H., Wan, J., Li, B., & Xia, T. (2015). Multi-view 3d object detection network for autonomous driving. IEEE Conference on Computer Vision and Pattern Recognition.

Esteva, A., Kuprel, B., Novoa, R. A., Ko, J., Swetter, S. M., Blau, H. M., & Thrun, S. (2017). Dermatologist-level classification of skin cancer with deep neural networks. Nature, 542(7639), 115-118.

He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep residual learning for image recognition. IEEE Conference on Computer Vision and Pattern Recognition.

Huang, G., Liu, Z., Van Der Maaten, L., & Weinberger, K. Q. (2017). Densely connected convolutional networks. IEEE Conference on Computer Vision and Pattern Recognition.

Krizhevsky, A., Sutskever, I., & Hinton, G. E. (2012). ImageNet classification with deep convolutional neural networks. Advances in Neural Information Processing Systems.

LeCun, Y., Bengio, Y., & Hinton, G. (2015). Deep learning. Nature, 521(7553), 436-444.

Real, E., Aggarwal, A., Huang, Y., & Le, Q. V. (2019). Regularized evolution for image classifier architecture search. Proceedings of the AAAI Conference on Artificial Intelligence.

Simonyan, K., & Zisserman, A. (2014). Very deep convolutional networks for large-scale image recognition. arXiv preprint arXiv:1409.1556.

Tan, M., & Le, Q. (2019). EfficientNet: Rethinking model scaling for convolutional neural networks. International Conference on Machine Learning."""

        page2.insert_text((50, 50), results_and_refs, fontsize=10, color=(0, 0, 0))

        doc.save(str(pdf_path))
        doc.close()
        self.fixtures[filename] = pdf_path
        return pdf_path

    def create_data_science_paper(self, filename: str = "data_science_sample.pdf") -> Path:
        """Create a sample data science research paper."""
        pdf_path = self.fixture_dir / filename
        doc = fitz.open()

        page1 = doc.new_page()

        content = """Machine Learning in Healthcare: Predictive Analytics for Patient Outcomes

Abstract

Healthcare systems generate vast amounts of data that can be leveraged for predictive analytics. This study examines machine learning approaches for predicting patient outcomes, focusing on readmission rates, mortality prediction, and treatment optimization. We evaluate various algorithms including random forests, gradient boosting, and neural networks on electronic health record data.

1. Introduction

The digitization of healthcare records has created unprecedented opportunities for data-driven medicine (Rajkomar et al., 2018). Machine learning techniques can identify patterns in patient data that may not be apparent to human clinicians, potentially improving diagnosis accuracy and treatment outcomes (Topol, 2019).

This paper presents a comprehensive analysis of ML applications in healthcare, with particular focus on:
- 30-day readmission prediction
- Mortality risk assessment
- Personalized treatment recommendations

2. Methodology

We analyzed a dataset of 50,000 patient records from multiple hospitals, including demographics, vital signs, lab results, and medication histories. Feature engineering included temporal aggregation of time-series data and creation of comorbidity indices (Charlson et al., 1987).

Models evaluated:
- Logistic Regression (baseline)
- Random Forest (Breiman, 2001)
- Gradient Boosting Machines (Chen & Guestrin, 2016)
- Deep Neural Networks (Goodfellow et al., 2016)

Performance metrics included AUROC, precision, recall, and calibration plots to assess clinical utility."""

        page1.insert_text((50, 50), content, fontsize=10, color=(0, 0, 0))

        # Page 2
        page2 = doc.new_page()

        results_refs = """3. Results

Random Forest achieved the highest AUROC of 0.87 for readmission prediction, outperforming logistic regression (0.81) and neural networks (0.84). Feature importance analysis revealed that previous admission history and comorbidity burden were the strongest predictors.

For mortality prediction, gradient boosting achieved 0.93 AUROC, with age, acute physiology scores, and organ failure indicators as top features. The model demonstrated good calibration across risk deciles.

4. Clinical Implications

These results suggest that machine learning can provide valuable decision support for clinicians. However, model interpretability remains crucial for clinical adoption (Rudin, 2019). Our feature importance analysis provides insights that align with clinical knowledge.

References

Breiman, L. (2001). Random forests. Machine Learning, 45(1), 5-32.

Charlson, M. E., Pompei, P., Ales, K. L., & MacKenzie, C. R. (1987). A new method of classifying prognostic comorbidity in longitudinal studies. Journal of Chronic Diseases, 40(5), 373-383.

Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining.

Goodfellow, I., Bengio, Y., & Courville, A. (2016). Deep Learning. MIT Press.

Rajkomar, A., Dean, J., & Kohane, I. (2019). Machine learning in medicine. New England Journal of Medicine, 380(14), 1347-1358.

Rudin, C. (2019). Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead. Nature Machine Intelligence, 1(5), 206-215.

Topol, E. J. (2019). High-performance medicine: the convergence of human and artificial intelligence. Nature Medicine, 25(1), 44-56."""

        page2.insert_text((50, 50), results_refs, fontsize=10, color=(0, 0, 0))

        doc.save(str(pdf_path))
        doc.close()
        self.fixtures[filename] = pdf_path
        return pdf_path

    def create_all_academic_fixtures(self) -> Dict[str, Path]:
        """Create all academic test fixtures."""
        print("Creating academic PDF test fixtures...")

        self.create_ai_research_paper()
        self.create_computer_vision_paper()
        self.create_data_science_paper()

        print(f"Created {len(self.fixtures)} academic PDF fixtures in {self.fixture_dir}")
        return self.fixtures.copy()

    def get_fixture_path(self, fixture_name: str) -> Optional[Path]:
        """Get path to a specific fixture."""
        return self.fixtures.get(fixture_name)

    def list_fixtures(self) -> List[str]:
        """List all available academic fixtures."""
        return list(self.fixtures.keys())

    def cleanup_fixtures(self):
        """Clean up created fixture files."""
        for fixture_path in self.fixtures.values():
            if fixture_path.exists():
                fixture_path.unlink()
        self.fixtures.clear()
        print(f"Cleaned up academic PDF fixtures in {self.fixture_dir}")


def create_academic_fixtures():
    """Convenience function to create academic test fixtures."""
    generator = AcademicPDFGenerator()
    return generator.create_all_academic_fixtures()


if __name__ == "__main__":
    # Create academic fixtures when run directly
    create_academic_fixtures()
    print("Academic PDF test fixtures created successfully!")