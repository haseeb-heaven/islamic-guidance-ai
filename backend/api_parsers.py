"""
API Response Parsers for Islamic Guidance AI
Comprehensive parsers for Quran.com API and Sunnah.com API responses
Handles multiple response formats, error cases, and data transformations
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import logging
import json
import re

# Configure logger
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS
# ============================================================================

class RevelationType(Enum):
    """Quran revelation types"""
    MECCAN = "Meccan"
    MEDINAN = "Medinan"
    UNKNOWN = "Unknown"


class HadithGrade(Enum):
    """Hadith authenticity grades"""
    SAHIH = "Sahih"
    HASAN = "Hasan"
    DAIF = "Daif"
    MAWDU = "Mawdu"
    UNKNOWN = "Unknown"


class APISource(Enum):
    """API source identifiers"""
    QURAN_COM = "quran.com"
    ALQURAN_CLOUD = "alquran.cloud"
    SUNNAH_COM = "sunnah.com"
    HADITH_API = "hadith-api"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class QuranVerse:
    """
    Represents a single Quran verse with complete metadata
    Supports multiple API response formats
    """
    # Core verse data
    verse_key: str  # Format: "chapter:verse" (e.g., "2:255")
    text_uthmani: str  # Arabic text in Uthmani script
    text_simple: str  # Simplified Arabic text
    text_translation: str  # English translation
    
    # Verse identifiers
    verse_number: int  # Absolute verse number in Quran
    verse_in_surah: int  # Verse number within surah
    
    # Surah metadata
    surah_number: int
    surah_name_arabic: str
    surah_name_english: str
    surah_name_translation: str
    revelation_type: RevelationType
    
    # Optional metadata
    juz_number: Optional[int] = None
    hizb_number: Optional[int] = None
    page_number: Optional[int] = None
    
    # Translation/Edition info
    translator_name: Optional[str] = None
    translation_id: Optional[str] = None
    
    # Search relevance
    relevance_score: Optional[float] = None
    highlighted_text: Optional[str] = None
    
    # Timestamps
    retrieved_at: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        """String representation"""
        return f"[Quran {self.verse_key}] {self.surah_name_english}"
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"QuranVerse(verse_key='{self.verse_key}', "
            f"surah='{self.surah_name_english}', "
            f"verse={self.verse_in_surah})"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert enums and datetime
        data['revelation_type'] = self.revelation_type.value
        data['retrieved_at'] = self.retrieved_at.isoformat()
        return data
    
    def to_citation(self) -> str:
        """Generate proper Islamic citation"""
        return f"[Quran {self.surah_name_english} {self.surah_number}:{self.verse_in_surah}]"
    
    def get_quran_com_url(self) -> str:
        """Get Quran.com URL for this verse"""
        return f"https://quran.com/{self.verse_key}"
    
    def format_for_display(self, include_arabic: bool = True) -> str:
        """
        Format verse for user-friendly display
        
        Args:
            include_arabic: Whether to include Arabic text
            
        Returns:
            Formatted string with verse details
        """
        lines = [
            f"📖 {self.surah_name_english} ({self.surah_name_arabic})",
            f"📍 Chapter {self.surah_number}, Verse {self.verse_in_surah}",
            f"🕌 Revelation: {self.revelation_type.value}",
            ""
        ]
        
        if include_arabic and self.text_uthmani:
            lines.append(f"Arabic: {self.text_uthmani}")
            lines.append("")
        
        lines.append(f'"{self.text_translation}"')
        lines.append("")
        lines.append(f"🔗 {self.get_quran_com_url()}")
        
        return "\n".join(lines)


@dataclass
class HadithNarration:
    """
    Represents a single Hadith with complete chain and metadata
    """
    # Core hadith data
    hadith_number: int  # Number in collection
    book_number: int  # Book within collection
    chapter_number: Optional[int] = None
    
    # Text content
    arabic_text: Optional[str] = None
    english_text: str = ""
    
    # Collection info
    collection_name: str = ""
    collection_id: str = ""
    book_name: str = ""
    chapter_name: Optional[str] = None
    
    # Authenticity
    grades: List[str] = field(default_factory=list)
    primary_grade: Optional[HadithGrade] = None
    
    # Chain of narration (Isnad)
    narrator_chain: List[str] = field(default_factory=list)
    
    # References
    references: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    volume_number: Optional[int] = None
    page_number: Optional[int] = None
    
    # Search relevance
    relevance_score: Optional[float] = None
    matched_keywords: List[str] = field(default_factory=list)
    
    # Timestamps
    retrieved_at: datetime = field(default_factory=datetime.now)
    
    def __str__(self) -> str:
        """String representation"""
        return f"[{self.collection_name} {self.hadith_number}]"
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"HadithNarration(collection='{self.collection_name}', "
            f"hadith_number={self.hadith_number}, "
            f"book={self.book_number})"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert enums and datetime
        if self.primary_grade:
            data['primary_grade'] = self.primary_grade.value
        data['retrieved_at'] = self.retrieved_at.isoformat()
        return data
    
    def to_citation(self) -> str:
        """Generate proper Islamic citation"""
        book_ref = f", Book {self.book_number}" if self.book_number else ""
        return f"[{self.collection_name}{book_ref}:{self.hadith_number}]"
    
    def get_sunnah_com_url(self) -> str:
        """Get Sunnah.com URL for this hadith"""
        if self.collection_id:
            return f"https://sunnah.com/{self.collection_id}:{self.hadith_number}"
        return f"https://sunnah.com/{self.collection_name.lower().replace(' ', '')}:{self.hadith_number}"
    
    def format_for_display(self, include_arabic: bool = False) -> str:
        """
        Format hadith for user-friendly display
        
        Args:
            include_arabic: Whether to include Arabic text
            
        Returns:
            Formatted string with hadith details
        """
        lines = [
            f"📚 {self.collection_name}",
            f"📖 Book {self.book_number}: {self.book_name}",
            f"📍 Hadith #{self.hadith_number}",
        ]
        
        if self.grades:
            lines.append(f"✅ Grade: {', '.join(self.grades)}")
        
        lines.append("")
        
        if include_arabic and self.arabic_text:
            lines.append(f"Arabic: {self.arabic_text}")
            lines.append("")
        
        lines.append(f'"{self.english_text}"')
        lines.append("")
        lines.append(f"🔗 {self.get_sunnah_com_url()}")
        
        return "\n".join(lines)


@dataclass
class SearchResult:
    """
    Aggregated search results from multiple sources
    """
    query: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Results
    quran_verses: List[QuranVerse] = field(default_factory=list)
    hadiths: List[HadithNarration] = field(default_factory=list)
    
    # Metadata
    total_quran_matches: int = 0
    total_hadith_matches: int = 0
    search_duration_ms: Optional[float] = None
    
    # Errors
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "query": self.query,
            "timestamp": self.timestamp.isoformat(),
            "quran_verses": [v.to_dict() for v in self.quran_verses],
            "hadiths": [h.to_dict() for h in self.hadiths],
            "total_quran_matches": self.total_quran_matches,
            "total_hadith_matches": self.total_hadith_matches,
            "search_duration_ms": self.search_duration_ms,
            "errors": self.errors
        }


# ============================================================================
# QURAN API PARSER
# ============================================================================

class QuranAPIParser:
    """
    Parser for Quran.com API v4 responses
    Handles multiple endpoints and response formats
    """
    
    # Default translations
    DEFAULT_TRANSLATION = "en.sahih"  # Sahih International
    POPULAR_TRANSLATIONS = {
        "en.sahih": "Saheeh International",
        "en.pickthall": "Pickthall",
        "en.yusufali": "Yusuf Ali",
        "en.hilali": "Hilali & Khan",
        "en.clear": "Clear Quran"
    }
    
    def __init__(self):
        """Initialize parser"""
        logger.info("✅ QuranAPIParser initialized")
    
    @staticmethod
    def parse_search_response(response: Dict[str, Any]) -> List[QuranVerse]:
        """
        Parse Quran.com search API response
        
        Args:
            response: Raw API response
            
        Returns:
            List of QuranVerse objects
        """
        verses = []
        
        try:
            # Extract search results
            search_data = response.get("search", {})
            results = search_data.get("results", [])
            
            logger.info(f"📥 Parsing {len(results)} Quran search results")
            
            for result in results:
                try:
                    verse = QuranAPIParser._parse_verse_result(result)
                    if verse:
                        verses.append(verse)
                except Exception as e:
                    logger.error(f"❌ Error parsing verse: {e}")
                    continue
            
            logger.info(f"✅ Successfully parsed {len(verses)} verses")
            
        except Exception as e:
            logger.error(f"❌ Error parsing search response: {e}")
        
        return verses
    
    @staticmethod
    def _parse_verse_result(result: Dict[str, Any]) -> Optional[QuranVerse]:
        """Parse a single verse from search results"""
        try:
            # Extract verse data
            verse_key = result.get("verse_key", "")
            if not verse_key:
                return None
            
            # Parse verse key (format: "chapter:verse")
            chapter, verse = map(int, verse_key.split(":"))
            
            # Extract translations
            translations = result.get("translations", [])
            translation_text = ""
            translator_name = None
            translation_id = None
            
            if translations:
                # Get first translation
                trans = translations[0]
                translation_text = QuranAPIParser._clean_html(
                    trans.get("text", "")
                )
                translator_name = trans.get("resource_name")
                translation_id = trans.get("resource_id")
            
            # Extract verse text (Arabic)
            text_uthmani = result.get("text", "")
            text_simple = result.get("text_simple", text_uthmani)
            
            # Extract chapter info
            chapter_info = result.get("chapter", {})
            
            # Determine revelation type
            revelation = chapter_info.get("revelation_place", "").lower()
            if "makkah" in revelation or "mecca" in revelation:
                rev_type = RevelationType.MECCAN
            elif "madinah" in revelation or "medina" in revelation:
                rev_type = RevelationType.MEDINAN
            else:
                rev_type = RevelationType.UNKNOWN
            
            # Create verse object
            verse = QuranVerse(
                verse_key=verse_key,
                text_uthmani=text_uthmani,
                text_simple=text_simple,
                text_translation=translation_text,
                verse_number=result.get("verse_id", 0),
                verse_in_surah=verse,
                surah_number=chapter,
                surah_name_arabic=chapter_info.get("name_arabic", ""),
                surah_name_english=chapter_info.get("name_simple", ""),
                surah_name_translation=chapter_info.get("translated_name", {}).get("name", ""),
                revelation_type=rev_type,
                juz_number=result.get("juz_number"),
                hizb_number=result.get("hizb_number"),
                page_number=result.get("page_number"),
                translator_name=translator_name,
                translation_id=translation_id,
                highlighted_text=result.get("highlighted", "")
            )
            
            return verse
            
        except Exception as e:
            logger.error(f"❌ Error parsing verse result: {e}")
            return None
    
    @staticmethod
    def parse_verse_by_key_response(response: Dict[str, Any]) -> Optional[QuranVerse]:
        """
        Parse response from verse by key endpoint
        
        Args:
            response: Raw API response
            
        Returns:
            QuranVerse object or None
        """
        try:
            verse_data = response.get("verse", {})
            if not verse_data:
                return None
            
            # Similar parsing logic as search results
            return QuranAPIParser._parse_verse_result(verse_data)
            
        except Exception as e:
            logger.error(f"❌ Error parsing verse by key: {e}")
            return None
    
    @staticmethod
    def parse_verses_by_chapter_response(response: Dict[str, Any]) -> List[QuranVerse]:
        """
        Parse response from verses by chapter endpoint
        
        Args:
            response: Raw API response
            
        Returns:
            List of QuranVerse objects
        """
        verses = []
        
        try:
            verses_data = response.get("verses", [])
            
            for verse_data in verses_data:
                verse = QuranAPIParser._parse_verse_result(verse_data)
                if verse:
                    verses.append(verse)
            
            logger.info(f"✅ Parsed {len(verses)} verses from chapter")
            
        except Exception as e:
            logger.error(f"❌ Error parsing chapter verses: {e}")
        
        return verses
    
    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags from text"""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        text = text.replace("&quot;", '"')
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&#39;", "'")
        
        return text.strip()
    
    @staticmethod
    def format_verses_for_display(verses: List[QuranVerse], limit: Optional[int] = None) -> str:
        """
        Format multiple verses for display
        
        Args:
            verses: List of verses
            limit: Maximum verses to display
            
        Returns:
            Formatted string
        """
        if not verses:
            return "No verses found."
        
        verses_to_show = verses[:limit] if limit else verses
        
        lines = [
            f"📖 Found {len(verses)} verse(s):",
            "=" * 60,
            ""
        ]
        
        for i, verse in enumerate(verses_to_show, 1):
            lines.append(f"{i}. {verse.format_for_display(include_arabic=False)}")
            lines.append("")
        
        if limit and len(verses) > limit:
            lines.append(f"... and {len(verses) - limit} more verse(s)")
        
        return "\n".join(lines)


# ============================================================================
# HADITH API PARSER
# ============================================================================

class HadithAPIParser:
    """
    Parser for Sunnah.com API and other Hadith APIs
    Handles multiple collections and formats
    """
    
    # Collection mappings
    COLLECTION_NAMES = {
        "eng-bukhari": "Sahih al-Bukhari",
        "eng-muslim": "Sahih Muslim",
        "eng-abudawud": "Sunan Abi Dawud",
        "eng-tirmidhi": "Jami` at-Tirmidhi",
        "eng-nasai": "Sunan an-Nasa'i",
        "eng-ibnmajah": "Sunan Ibn Majah",
        "eng-malik": "Muwatta Malik",
        "eng-riyadussaliheen": "Riyad as-Salihin",
        "eng-adab": "Al-Adab Al-Mufrad",
        "eng-bulugh": "Bulugh al-Maram",
        "eng-nawawi40": "40 Hadith Nawawi",
        "eng-qudsi40": "40 Hadith Qudsi"
    }
    
    COLLECTION_ALIASES = {
        "bukhari": "eng-bukhari",
        "muslim": "eng-muslim",
        "abu dawud": "eng-abudawud",
        "tirmidhi": "eng-tirmidhi",
        "nasai": "eng-nasai",
        "ibn majah": "eng-ibnmajah"
    }
    
    def __init__(self):
        """Initialize parser"""
        logger.info("✅ HadithAPIParser initialized")
    
    @staticmethod
    def parse_collection_response(
        response: Union[Dict[str, Any], List[Dict[str, Any]]],
        collection_id: str
    ) -> List[HadithNarration]:
        """
        Parse Hadith API collection response
        
        Args:
            response: Raw API response (dict or list)
            collection_id: Collection identifier
            
        Returns:
            List of HadithNarration objects
        """
        hadiths = []
        
        try:
            # Handle different response formats
            if isinstance(response, dict):
                hadith_data = response.get("hadiths", response.get("data", []))
            elif isinstance(response, list):
                hadith_data = response
            else:
                logger.error(f"❌ Unexpected response type: {type(response)}")
                return []
            
            logger.info(f"📥 Parsing {len(hadith_data)} hadiths from {collection_id}")
            
            collection_name = HadithAPIParser.COLLECTION_NAMES.get(
                collection_id,
                collection_id
            )
            
            for data in hadith_data:
                try:
                    hadith = HadithAPIParser._parse_hadith(data, collection_id, collection_name)
                    if hadith:
                        hadiths.append(hadith)
                except Exception as e:
                    logger.error(f"❌ Error parsing hadith: {e}")
                    continue
            
            logger.info(f"✅ Successfully parsed {len(hadiths)} hadiths")
            
        except Exception as e:
            logger.error(f"❌ Error parsing collection response: {e}")
        
        return hadiths
    
    @staticmethod
    def _parse_hadith(
        data: Dict[str, Any],
        collection_id: str,
        collection_name: str
    ) -> Optional[HadithNarration]:
        """Parse a single hadith from data"""
        try:
            # Extract hadith number
            hadith_number = data.get("hadithNumber", data.get("hadithnumber", 0))
            if isinstance(hadith_number, str):
                # Extract numeric part
                hadith_number = int(re.search(r'\d+', hadith_number).group())
            
            # Extract book info
            book_number = data.get("book", data.get("bookNumber", 0))
            book_name = data.get("bookName", data.get("book_name", ""))
            
            # Extract chapter info
            chapter_number = data.get("chapter", data.get("chapterNumber"))
            chapter_name = data.get("chapterName", data.get("chapter_name"))
            
            # Extract text
            english_text = ""
            arabic_text = None
            
            # Try different text field structures
            if "hadith" in data:
                hadith_texts = data["hadith"]
                if isinstance(hadith_texts, list):
                    for text_obj in hadith_texts:
                        if text_obj.get("lang") == "en":
                            english_text = text_obj.get("body", "")
                        elif text_obj.get("lang") == "ar":
                            arabic_text = text_obj.get("body")
                elif isinstance(hadith_texts, dict):
                    english_text = hadith_texts.get("body", "")
            
            if not english_text:
                english_text = data.get("text", data.get("body", ""))
            
            if not arabic_text:
                arabic_text = data.get("arabicText", data.get("arabic"))
            
            # Clean HTML from text
            english_text = HadithAPIParser._clean_html(english_text)
            if arabic_text:
                arabic_text = HadithAPIParser._clean_html(arabic_text)
            
            # Extract grades
            grades = []
            primary_grade = None
            
            if "grades" in data:
                grades_data = data["grades"]
                if isinstance(grades_data, list):
                    for grade_obj in grades_data:
                        if isinstance(grade_obj, dict):
                            grade = grade_obj.get("grade", "")
                        else:
                            grade = str(grade_obj)
                        grades.append(grade)
                        
                        # Determine primary grade
                        if not primary_grade:
                            grade_lower = grade.lower()
                            if "sahih" in grade_lower:
                                primary_grade = HadithGrade.SAHIH
                            elif "hasan" in grade_lower:
                                primary_grade = HadithGrade.HASAN
                            elif "daif" in grade_lower or "weak" in grade_lower:
                                primary_grade = HadithGrade.DAIF
            
            # Extract references
            references = data.get("reference", data.get("references", {}))
            
            # Extract narrator chain if available
            narrator_chain = []
            if "chain" in data:
                narrator_chain = data["chain"]
            
            # Create hadith object
            hadith = HadithNarration(
                hadith_number=hadith_number,
                book_number=book_number,
                chapter_number=chapter_number,
                arabic_text=arabic_text,
                english_text=english_text,
                collection_name=collection_name,
                collection_id=collection_id,
                book_name=book_name,
                chapter_name=chapter_name,
                grades=grades,
                primary_grade=primary_grade,
                narrator_chain=narrator_chain,
                references=references if isinstance(references, dict) else {},
                volume_number=data.get("volume")
            )
            
            return hadith
            
        except Exception as e:
            logger.error(f"❌ Error parsing hadith data: {e}")
            return None
    
    @staticmethod
    def search_by_text(
        hadiths: List[HadithNarration],
        keyword: str,
        case_sensitive: bool = False,
        limit: Optional[int] = None
    ) -> List[HadithNarration]:
        """
        Search hadiths by text content
        
        Args:
            hadiths: List of hadiths to search
            keyword: Search keyword
            case_sensitive: Whether search is case sensitive
            limit: Maximum results to return
            
        Returns:
            Filtered list of hadiths
        """
        keyword_search = keyword if case_sensitive else keyword.lower()
        results = []
        
        for hadith in hadiths:
            text_search = hadith.english_text if case_sensitive else hadith.english_text.lower()
            
            if keyword_search in text_search:
                # Calculate relevance (simple word count)
                relevance = text_search.count(keyword_search)
                hadith.relevance_score = float(relevance)
                hadith.matched_keywords = [keyword]
                results.append(hadith)
            
            if limit and len(results) >= limit:
                break
        
        # Sort by relevance
        results.sort(key=lambda h: h.relevance_score or 0, reverse=True)
        
        return results
    
    @staticmethod
    def filter_by_grade(
        hadiths: List[HadithNarration],
        min_grade: HadithGrade = HadithGrade.HASAN
    ) -> List[HadithNarration]:
        """Filter hadiths by minimum authenticity grade"""
        grade_order = [
            HadithGrade.SAHIH,
            HadithGrade.HASAN,
            HadithGrade.DAIF,
            HadithGrade.MAWDU,
            HadithGrade.UNKNOWN
        ]
        
        min_index = grade_order.index(min_grade)
        
        return [
            h for h in hadiths
            if h.primary_grade and grade_order.index(h.primary_grade) <= min_index
        ]
    
    @staticmethod
    def _clean_html(text: str) -> str:
        """Remove HTML tags and clean text"""
        if not text:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Decode HTML entities
        text = text.replace("&quot;", '"')
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    @staticmethod
    def format_hadiths_for_display(
        hadiths: List[HadithNarration],
        limit: Optional[int] = None
    ) -> str:
        """
        Format multiple hadiths for display
        
        Args:
            hadiths: List of hadiths
            limit: Maximum hadiths to display
            
        Returns:
            Formatted string
        """
        if not hadiths:
            return "No hadiths found."
        
        hadiths_to_show = hadiths[:limit] if limit else hadiths
        
        lines = [
            f"📚 Found {len(hadiths)} hadith(s):",
            "=" * 60,
            ""
        ]
        
        for i, hadith in enumerate(hadiths_to_show, 1):
            lines.append(f"{i}. {hadith.format_for_display(include_arabic=False)}")
            lines.append("")
        
        if limit and len(hadiths) > limit:
            lines.append(f"... and {len(hadiths) - limit} more hadith(s)")
        
        return "\n".join(lines)


# ============================================================================
# RESPONSE FORMATTER
# ============================================================================

class IslamicResponseFormatter:
    """
    Formats parsed data into user-friendly responses
    Combines Quran and Hadith data for comprehensive guidance
    """
    
    @staticmethod
    def format_guidance_response(
        query: str,
        quran_verses: List[QuranVerse],
        hadiths: List[HadithNarration],
        ai_guidance: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format complete guidance response
        
        Args:
            query: Original user query
            quran_verses: List of relevant Quran verses
            hadiths: List of relevant hadiths
            ai_guidance: Optional AI-generated guidance
            
        Returns:
            Formatted response dictionary
        """
        response = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "guidance": {},
            "sources": {
                "quran": [],
                "hadith": []
            },
            "summary": {
                "total_verses": len(quran_verses),
                "total_hadiths": len(hadiths),
                "has_ai_guidance": ai_guidance is not None
            }
        }
        
        # Add AI guidance if available
        if ai_guidance:
            response["guidance"]["ai"] = ai_guidance
        
        # Format Quran verses
        for verse in quran_verses:
            response["sources"]["quran"].append({
                "reference": verse.to_citation(),
                "text": verse.text_translation,
                "url": verse.get_quran_com_url(),
                "chapter": verse.surah_number,
                "verse": verse.verse_in_surah,
                "surah_name": verse.surah_name_english
            })
        
        # Format Hadiths
        for hadith in hadiths:
            response["sources"]["hadith"].append({
                "reference": hadith.to_citation(),
                "text": hadith.english_text,
                "url": hadith.get_sunnah_com_url(),
                "collection": hadith.collection_name,
                "hadith_number": hadith.hadith_number,
                "grades": hadith.grades
            })
        
        return response
    
    @staticmethod
    def format_citation_list(
        quran_verses: List[QuranVerse],
        hadiths: List[HadithNarration]
    ) -> str:
        """Generate formatted citation list"""
        lines = ["📚 References:", ""]
        
        if quran_verses:
            lines.append("Quran:")
            for v in quran_verses:
                lines.append(f"  • {v.to_citation()}")
            lines.append("")
        
        if hadiths:
            lines.append("Hadith:")
            for h in hadiths:
                lines.append(f"  • {h.to_citation()}")
        
        return "\n".join(lines)


# ============================================================================
# MAIN PARSER INTERFACE
# ============================================================================

def parse_quran_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Main function to parse Quran API responses
    Returns list of dictionaries for easy JSON serialization
    """
    parser = QuranAPIParser()
    verses = parser.parse_search_response(response)
    return [v.to_dict() for v in verses]


def parse_hadith_response(response: Union[Dict, List], collection_id: str = "eng-bukhari") -> List[Dict[str, Any]]:
    """
    Main function to parse Hadith API responses
    Returns list of dictionaries for easy JSON serialization
    """
    parser = HadithAPIParser()
    hadiths = parser.parse_collection_response(response, collection_id)
    return [h.to_dict() for h in hadiths]


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Data classes
    'QuranVerse',
    'HadithNarration',
    'SearchResult',
    
    # Enums
    'RevelationType',
    'HadithGrade',
    'APISource',
    
    # Parsers
    'QuranAPIParser',
    'HadithAPIParser',
    'IslamicResponseFormatter',
    
    # Main functions
    'parse_quran_response',
    'parse_hadith_response'
]


if __name__ == "__main__":
    # Test the parsers
    print("✅ Islamic API Parsers Module Loaded")
    print(f"📊 Exports: {', '.join(__all__)}")
