import os
import sys
import unittest

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.config import load_config
from core.document_loader import DocumentLoader, LoadedDocument
from core.chunker import SemanticChunker
from core.embeddings import EmbeddingEngine
from core.vector_store import VectorStore
from core.retriever import HybridRetriever
from core.summarizer import DocumentSummarizer
from core.document_generator import DocumentGenerator
from core.latency_tracker import LatencyTracker

class TestRAGPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.config = load_config()
        cls.emb_engine = EmbeddingEngine(provider="gemini", model_name=cls.config.models.embedding_model)
        cls.v_store = VectorStore()
        cls.chunker = SemanticChunker(chunk_size=cls.config.rag.chunk_size, chunk_overlap=cls.config.rag.chunk_overlap)
        cls.retriever = HybridRetriever(
            vector_store=cls.v_store,
            embedding_engine=cls.emb_engine,
            alpha=cls.config.rag.hybrid_alpha,
            top_k=cls.config.rag.top_k,
            similarity_threshold=0.1
        )
        cls.summarizer = DocumentSummarizer(
            provider="gemini",
            llm_model=cls.config.models.llm_model,
            chunker=cls.chunker,
            retriever=cls.retriever
        )
        cls.doc_gen = DocumentGenerator(
            retriever=cls.retriever,
            provider="gemini",
            llm_model=cls.config.models.llm_model
        )

    def test_01_document_loading(self):
        sample_path = os.path.join(BASE_DIR, "samples", "remsl_mandi_trading_sop.md")
        doc = DocumentLoader.load_file(sample_path)
        self.assertIsNotNone(doc)
        self.assertEqual(doc.file_type, "markdown")
        self.assertGreater(len(doc.content), 100)
        self.assertGreater(len(doc.sections), 0)

    def test_02_chunking(self):
        sample_path = os.path.join(BASE_DIR, "samples", "remsl_mandi_trading_sop.md")
        doc = DocumentLoader.load_file(sample_path)
        chunks = self.chunker.chunk_document(doc)
        self.assertGreater(len(chunks), 0)
        for c in chunks:
            self.assertIsNotNone(c.chunk_id)
            self.assertIsNotNone(c.text)
            self.assertIn("chunk_index", c.metadata)

    def test_03_embedding_and_vector_store(self):
        sample_path = os.path.join(BASE_DIR, "samples", "remsl_mandi_trading_sop.md")
        doc = DocumentLoader.load_file(sample_path)
        chunks = self.chunker.chunk_document(doc)
        embs = self.emb_engine.embed_batch([c.text for c in chunks])
        self.assertEqual(len(chunks), len(embs))
        self.v_store.add_chunks(chunks, embs)
        self.assertGreaterEqual(len(self.v_store.get_all_chunks()), len(chunks))

    def test_04_hybrid_retrieval(self):
        self.retriever._sync_bm25()
        tracker = LatencyTracker("Test_Hybrid_Retrieval")
        results = self.retriever.retrieve("escrow account APMC cess 1.5%", top_k=3, tracker=tracker)
        self.assertGreater(len(results), 0)
        top_res = results[0]
        self.assertGreater(top_res.score, 0.0)
        self.assertIsNotNone(top_res.chunk.text)
        self.assertLess(tracker.total_latency_ms, 2000)

    def test_05_summarization_strategies(self):
        sample_path = os.path.join(BASE_DIR, "samples", "neml_payment_gateway_spec.md")
        doc = DocumentLoader.load_file(sample_path)
        
        # Test Stuff
        stuff_res = self.summarizer.summarize_stuff(doc)
        self.assertIsNotNone(stuff_res.summary_text)
        self.assertEqual(stuff_res.strategy, "stuff")

        # Test Map-Reduce
        mr_res = self.summarizer.summarize_map_reduce(doc)
        self.assertIsNotNone(mr_res.summary_text)
        self.assertEqual(mr_res.strategy, "map_reduce")

    def test_06_document_generation(self):
        gen_doc = self.doc_gen.generate_document(
            document_title="Test Mandi SOP",
            document_type="Standard Operating Procedure",
            user_instructions="Detail the 4 auction bidding modes and DBT settlement.",
            top_k=3
        )
        self.assertIsNotNone(gen_doc.content_markdown)
        self.assertGreater(len(gen_doc.content_markdown), 50)
        self.assertIsNotNone(gen_doc.latency_report)

    def test_07_ollama_provider_switching(self):
        # Switch to Ollama provider
        self.emb_engine.set_provider("ollama", model_name="nomic-embed-text")
        self.summarizer.set_provider("ollama", model_name="llama3:8b")
        self.doc_gen.set_provider("ollama", model_name="llama3:8b")

        self.assertEqual(self.emb_engine.provider, "ollama")
        self.assertEqual(self.summarizer.provider, "ollama")
        self.assertEqual(self.doc_gen.provider, "ollama")

        # Test offline/diagnostic fallback when Ollama service isn't active
        doc = LoadedDocument(filename="test.txt", filepath="memory://test.txt", file_type="txt", content="Sample text content")
        res = self.summarizer.summarize_stuff(doc)
        self.assertIsNotNone(res.summary_text)

        # Reset back to Gemini
        self.emb_engine.set_provider("gemini")
        self.summarizer.set_provider("gemini")
        self.doc_gen.set_provider("gemini")

    def test_08_latency_tracker(self):
        tracker = LatencyTracker("Test_Tracker")
        tracker.start_stage("Stage_1")
        tracker.end_stage()
        tracker.start_stage("Stage_2")
        tracker.record_ttft()
        tracker.finish(tokens_generated=150)
        
        breakdown = tracker.get_breakdown()
        self.assertIn("total_latency_ms", breakdown)
        self.assertIn("ttft_ms", breakdown)
        self.assertEqual(breakdown["tokens_generated"], 150)

    def test_09_secure_sql_agent(self):
        from core.db_connector import SecurePostgresConnector
        from core.sql_agent import SecureSQLAgent

        db = SecurePostgresConnector()
        agent = SecureSQLAgent(db_connector=db)

        # Test security violation blocking destructive SQL
        bad_res = db.execute_safe_query("DROP TABLE users;")
        self.assertFalse(bad_res["success"])
        self.assertIn("Security Violation", bad_res["error"])

        # Test stacked query blocking
        stacked_res = db.execute_safe_query("SELECT 1; SELECT 2;")
        self.assertFalse(stacked_res["success"])
        self.assertIn("Security Violation", stacked_res["error"])

        # Test dynamic PII masking
        test_rows = [
            {"user_id": "U101", "mobile_no": "9845012345", "email": "test.user@company.com", "address": "123 Main St, Suite 400", "bank_account": "123456789012"}
        ]
        masked = db._apply_pii_masking(test_rows)
        self.assertEqual(masked[0]["mobile_no"], "+91 ******2345")
        self.assertEqual(masked[0]["bank_account"], "******9012")
        self.assertIn("***", masked[0]["email"])

if __name__ == "__main__":
    unittest.main()
