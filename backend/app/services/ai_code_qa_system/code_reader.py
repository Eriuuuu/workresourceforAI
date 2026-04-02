import os
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

class DynamicCodeReader:
    """动态代码读取器 - 直接从文件系统读取完整代码"""
    
    def __init__(self, codebase_path: str):
        self.codebase_path = Path(codebase_path)
        self.supported_extensions = {'.cpp', '.cc', '.cxx', '.c', '.h', '.hpp', '.hxx', '.hh'}
    
    def read_entire_file(self, relative_path: str) -> str:
        """读取整个文件内容"""
        try:
            full_path = self.codebase_path / relative_path
            
            if not full_path.exists():
                return f"错误: 文件不存在 - {relative_path}"
            
            if not self._is_cpp_file(full_path):
                return f"错误: 不是C++文件 - {relative_path}"
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return content
            
        except PermissionError:
            return f"错误: 没有权限读取文件 - {relative_path}"
        except Exception as e:
            return f"错误: 读取文件失败 - {str(e)}"
    
    def read_file_section(self, relative_path: str, line_start: int, line_end: int) -> str:
        """读取文件的指定行范围"""
        try:
            full_path = self.codebase_path / relative_path
            
            if not full_path.exists():
                return f"错误: 文件不存在 - {relative_path}"
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # 调整行号范围
            start_idx = max(0, line_start - 1)
            end_idx = min(len(lines), line_end)
            
            if start_idx >= end_idx:
                return f"错误: 无效的行范围 {line_start}-{line_end}"
            
            selected_lines = lines[start_idx:end_idx]
            
            # 添加上下文信息
            result = f"// 文件: {relative_path} 第{line_start}-{line_end}行\n"
            for i, line in enumerate(selected_lines, start=line_start):
                result += f"{i:4d}: {line}"
            
            return result
            
        except Exception as e:
            return f"错误: 读取文件失败 - {str(e)}"
    
    def read_multiple_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """读取多个文件"""
        results = []
        
        for file_path in file_paths:
            content = self.read_entire_file(file_path)
            results.append({
                'file_path': file_path,
                'content': content,
                'success': not content.startswith('错误:'),
                'file_size': len(content)
            })
        
        return results
    
    def _is_cpp_file(self, file_path: Path) -> bool:
        """判断是否为C++文件"""
        return file_path.is_file() and file_path.suffix.lower() in self.supported_extensions
    
    def get_codebase_info(self) -> Dict[str, Any]:
        """获取代码库信息"""
        total_files = 0
        total_size = 0
        file_types = {}
        
        for file_path in self.codebase_path.rglob('*'):
            if self._is_cpp_file(file_path):
                total_files += 1
                file_size = file_path.stat().st_size
                total_size += file_size
                
                # 统计文件类型
                ext = file_path.suffix.lower()
                file_types[ext] = file_types.get(ext, 0) + 1
        
        return {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'file_types': file_types,
            'codebase_path': str(self.codebase_path)
        }