# LangChain文档处理器
# 定义了一个C++文档处理器，用于加载和分割C++代码文件
import os
from pathlib import Path
from typing import List, Dict, Any, Iterator
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import TextLoader
import hashlib
from loguru import logger


class CppDocumentProcessor:
    """C++文档处理器 - 使用LangChain处理代码文档"""
    
    def __init__(self, codebase_path: str, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.codebase_path = Path(codebase_path)
        self.supported_extensions = {'.cpp', '.cc', '.cxx', '.c', '.h', '.hpp', '.hxx', '.hh'}
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\nclass ", "\nstruct ", "\nnamespace ", "\nvoid ", "\nint ", "\nbool ", "\n\n", "\n", " ", ""]
        )
    
    def load_code_documents(self) -> List[Document]:
        """加载所有C++代码文档"""
        logger.info("开始加载C++代码文档...")
        
        all_documents = []
        file_count = 0
        error_count = 0
        
        for file_path in self.codebase_path.rglob('*'):
            if self._is_cpp_file(file_path):
                try:
                    file_docs = self._load_single_file(file_path)
                    all_documents.extend(file_docs)
                    file_count += 1
                    
                    if file_count % 50 == 0:
                        logger.info(f"已加载 {file_count} 个文件...")
                        
                except Exception as e:
                    logger.error(f"加载文件 {file_path} 失败: {e}")
                    error_count += 1
        
        logger.info(f"✓ 文档加载完成: {file_count} 个文件, {len(all_documents)} 个文档块, {error_count} 个错误")
        return all_documents
    
    def _is_cpp_file(self, file_path: Path) -> bool:
        """判断是否为C++文件"""
        return file_path.is_file() and file_path.suffix.lower() in self.supported_extensions
    
    def _load_single_file(self, file_path: Path) -> List[Document]:
        """加载单个文件并分割"""
        relative_path = str(file_path.relative_to(self.codebase_path))
        
        try:
            # 使用LangChain的TextLoader
            loader = TextLoader(str(file_path), encoding='utf-8', autodetect_encoding=True)
            documents = loader.load()
            
            # 为每个文档添加元数据
            for doc in documents:
                doc.metadata.update({
                    'file_path': relative_path,
                    'file_name': file_path.name,
                    'file_type': 'cpp',
                    'source_type': 'code_file',
                    'content_hash': hashlib.md5(doc.page_content.encode()).hexdigest()
                })
            
            # 分割文档
            split_docs = self.text_splitter.split_documents(documents)
            
            # 为分割后的文档添加更多元数据
            for i, doc in enumerate(split_docs):
                doc.metadata.update({
                    'chunk_id': i,
                    'total_chunks': len(split_docs)
                })
            
            return split_docs
            
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                loader = TextLoader(str(file_path), encoding='latin-1')
                documents = loader.load()
                
                for doc in documents:
                    doc.metadata.update({
                        'file_path': relative_path,
                        'file_name': file_path.name,
                        'file_type': 'cpp',
                        'source_type': 'code_file',
                        'content_hash': hashlib.md5(doc.page_content.encode()).hexdigest()
                    })
                
                split_docs = self.text_splitter.split_documents(documents)
                for i, doc in enumerate(split_docs):
                    doc.metadata.update({
                        'chunk_id': i,
                        'total_chunks': len(split_docs)
                    })
                
                return split_docs
                
            except Exception as e:
                logger.error(f"无法加载文件 {file_path}: {e}")
                return []
        
        except Exception as e:
            logger.error(f"加载文件 {file_path} 时出错: {e}")
            return []
    
    def get_file_statistics(self) -> Dict[str, Any]:
        """获取文件统计信息"""
        total_files = 0
        total_size = 0
        
        for file_path in self.codebase_path.rglob('*'):
            if self._is_cpp_file(file_path):
                total_files += 1
                total_size += file_path.stat().st_size
        
        return {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'supported_extensions': list(self.supported_extensions)
        }