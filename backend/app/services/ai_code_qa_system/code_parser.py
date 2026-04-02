import os
import re
import clang.cindex
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger
from dataclasses import dataclass

@dataclass
class CppEntity:
    """C++实体基类"""
    type: str
    name: str
    file_path: str
    line_start: int
    line_end: int
    namespace: str = ""
    signature: str = ""
    parent: Optional[str] = None
    visibility: str = "public"  # public, private, protected
    is_template: bool = False
    is_virtual: bool = False
    is_static: bool = False
    is_const: bool = False
    return_type: str = ""
    parameters: List[Dict[str, str]] = None  # name:type
    
    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'type': self.type,
            'name': self.name,
            'file_path': self.file_path,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'namespace': self.namespace,
            'signature': self.signature,
            'parent': self.parent,
            'visibility': self.visibility,
            'is_template': self.is_template,
            'is_virtual': self.is_virtual,
            'is_static': self.is_static,
            'is_const': self.is_const,
            'return_type': self.return_type,
            'parameters': self.parameters
        }


class AdvancedCppCodeParser:
    """高级C++代码解析器 - 使用libclang进行更准确的解析"""
    
    def __init__(self, codebase_path: str):
        self.codebase_path = Path(codebase_path)
        self.supported_extensions = {'.cpp', '.cc', '.cxx', '.c', '.h', '.hpp', '.hxx', '.hh'}
        
        # 配置libclang
        try:
            # 尝试自动查找libclang路径
            self._configure_clang()
            
        except Exception as e:
            logger.warning(f"libclang配置失败，使用正则解析模式: {e}")
            self.use_clang = False
            
        
        # 正则表达式模式（作为后备方案）
        self._init_regex_patterns()
    
    def _configure_clang(self):
        """配置libclang"""
        # 尝试常见的libclang路径
        possible_paths = [
            '/usr/lib/llvm-*/lib/libclang.so',  # Ubuntu
            '/usr/local/opt/llvm/lib/libclang.dylib',  # macOS Homebrew
            'C:/Program Files/LLVM/bin/libclang.dll',  # Windows
            'D:/LLVM/bin/libclang.dll',
            'C:/LLVM/bin/libclang.dll',
            '/usr/lib/x86_64-linux-gnu/libclang.so*',  # Linux
        ]
        
        for path_pattern in possible_paths:
            import glob
            matches = glob.glob(path_pattern)
            if matches:
                clang.cindex.Config.set_library_file(matches[0])
                self.use_clang = False
                logger.info(f"找到libclang库: {matches[0]}")
                return
        
        # 如果没有找到，尝试使用环境变量
        if os.getenv('LIBCLANG_PATH'):
            clang.cindex.Config.set_library_file(os.getenv('LIBCLANG_PATH'))
            self.use_clang = True
            logger.info(f"使用环境变量中的libclang库: {os.getenv('LIBCLANG_PATH')}")
            return
        
        # 如果都没有找到，将使用正则表达式模式
        self.use_clang = False
        logger.warning("未找到libclang库，使用正则表达式解析")
    
    def _init_regex_patterns(self):
        """初始化正则表达式模式"""
        # 更复杂的C++模式
        self.patterns = {
            # 命名空间
            'namespace': re.compile(r'^\s*namespace\s+(\w+)\s*{'),
            
            # 类定义（支持模板、继承、多行）
            'class': re.compile(r'^\s*(?:template\s*<[^>]+>\s*)?class\s+(\w+)\b'),
            
            # 结构体定义
            'struct': re.compile(r'^\s*(?:template\s*<[^>]+>\s*)?struct\s+(\w+)\b'),
            
            # 枚举定义
            'enum': re.compile(r'^\s*(?:class\s+)?enum(?:\s+class)?\s+(\w+)\b'),
            
            # 函数定义（支持复杂返回类型、模板、多行参数）
            'function_declaration': re.compile(r'^\s*(?:virtual\s+)?(?:inline\s+)?(?:static\s+)?'
                                              r'(?:constexpr\s+)?(?:explicit\s+)?'
                                              r'(?:template\s*<[^>]+>\s*)?'
                                              r'(\w+(?:<[^>]+>)?(?:\s*[*&]+)?\s+)?'  # 返回类型
                                              r'(\w+)\s*'  # 函数名
                                              r'\(([^)]*(?:\n[^)]*)*)\)'  # 参数（支持多行）
                                              r'\s*(?:const)?\s*(?:=\s*0)?\s*(?:override)?\s*[;{]'),
            
            # 构造函数/析构函数
            'constructor': re.compile(r'^\s*(?:explicit\s+)?(\~?\w+)\s*'
                                     r'\(([^)]*(?:\n[^)]*)*)\)\s*'
                                     r'(?::\s*[^{]*)?\s*[;{]'),
            
            # 宏定义
            'macro': re.compile(r'^\s*#\s*define\s+(\w+)\b'),
            
            # typedef/using
            'type_alias': re.compile(r'^\s*(?:typedef\s+.*\s+(\w+)\s*;|'
                                    r'using\s+(\w+)\s*=)'),
        }
        
        # 用于提取参数的正则
        self.param_pattern = re.compile(r'(\w+(?:<[^>]+>)?(?:\s*[*&]+)?)\s+(\w+)(?:\s*=\s*[^,)]+)?')
    
    def parse_codebase_entities(self) -> List[Dict[str, Any]]:
        """解析整个代码库的结构实体"""
        logger.info("开始解析C++代码结构...")
        
        all_entities = []
        file_count = 0
        error_count = 0
        
        for file_path in self.codebase_path.rglob('*'):
            if self._is_cpp_file(file_path):
                try:
                    if self.use_clang:
                        entities = self._parse_file_with_clang(file_path)
                    else:
                        entities = self._parse_file_with_regex(file_path)
                    
                    all_entities.extend(entities)
                    file_count += 1
                    
                    if file_count % 50 == 0:
                        logger.info(f"已解析 {file_count} 个文件...")
                        
                except Exception as e:
                    logger.error(f"解析文件 {file_path} 失败: {e}")
                    error_count += 1
        
        logger.info(f"✓ 代码结构解析完成: {file_count} 个文件, {len(all_entities)} 个实体, {error_count} 个错误")
        return all_entities
    
    def _is_cpp_file(self, file_path: Path) -> bool:
        """判断是否为C++文件"""
        return file_path.is_file() and file_path.suffix.lower() in self.supported_extensions
    
    def _parse_file_with_clang(self, file_path: Path) -> List[Dict[str, Any]]:
        """使用libclang解析文件"""
        entities = []
        relative_path = str(file_path.relative_to(self.codebase_path))
        
        # 解析文件
        index = clang.cindex.Index.create()
        translation_unit = index.parse(str(file_path))
        
        # 遍历AST
        for node in translation_unit.cursor.walk_preorder():
            if node.location.file and node.location.file.name == str(file_path):
                entity = self._clang_node_to_entity(node, relative_path)
                if entity:
                    entities.append(entity.to_dict())
        
        return entities
    
    def _clang_node_to_entity(self, node, file_path: str) -> Optional[CppEntity]:
        """将Clang AST节点转换为实体"""
        # 获取行号
        line_start = node.location.line
        # 对于复杂节点，尝试获取结束行
        line_end = line_start
        if node.extent.end.file == node.location.file:
            line_end = node.extent.end.line
        
        # 根据节点类型创建实体
        if node.kind == clang.cindex.CursorKind.NAMESPACE:
            return CppEntity(
                type='namespace',
                name=node.spelling,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end
            )
        
        elif node.kind == clang.cindex.CursorKind.CLASS_DECL:
            return CppEntity(
                type='class',
                name=node.spelling,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                signature=self._get_clang_signature(node)
            )
        
        elif node.kind == clang.cindex.CursorKind.STRUCT_DECL:
            return CppEntity(
                type='struct',
                name=node.spelling,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                signature=self._get_clang_signature(node)
            )
        
        elif node.kind in [clang.cindex.CursorKind.FUNCTION_DECL,
                          clang.cindex.CursorKind.CXX_METHOD]:
            # 提取参数信息
            parameters = []
            for arg in node.get_arguments():
                param_type = arg.type.spelling
                param_name = arg.spelling
                parameters.append({'name': param_name, 'type': param_type})
            
            # 判断是否为模板
            is_template = any(child.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER
                             for child in node.get_children())
            
            return CppEntity(
                type='function',
                name=node.spelling,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                return_type=node.result_type.spelling if node.result_type else '',
                parameters=parameters,
                is_template=is_template,
                is_static=node.is_static_method(),
                is_virtual=node.is_virtual_method(),
                signature=self._get_clang_signature(node)
            )
        
        elif node.kind == clang.cindex.CursorKind.CONSTRUCTOR:
            parameters = []
            for arg in node.get_arguments():
                param_type = arg.type.spelling
                param_name = arg.spelling
                parameters.append({'name': param_name, 'type': param_type})
            
            return CppEntity(
                type='constructor',
                name=node.spelling,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                parameters=parameters,
                signature=self._get_clang_signature(node)
            )
        
        elif node.kind == clang.cindex.CursorKind.DESTRUCTOR:
            return CppEntity(
                type='destructor',
                name=node.spelling,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                signature=self._get_clang_signature(node)
            )
        
        elif node.kind == clang.cindex.CursorKind.ENUM_DECL:
            return CppEntity(
                type='enum',
                name=node.spelling,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end
            )
        
        return None
    
    def _get_clang_signature(self, node) -> str:
        """获取节点的签名"""
        try:
            return node.type.spelling if node.type else node.spelling
        except:
            return node.spelling
    
    def _parse_file_with_regex(self, file_path: Path) -> List[Dict[str, Any]]:
        """使用正则表达式解析文件（后备方案）"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        entities = []
        relative_path = str(file_path.relative_to(self.codebase_path))
        
        # 添加文件实体
        entities.append({
            'type': 'file',
            'name': file_path.name,
            'file_path': relative_path,
            'line_start': 1,
            'line_end': len(content.split('\n'))
        })
        
        # 按行处理，记录更多上下文
        lines = content.split('\n')
        current_namespace = ""
        current_class = ""
        
        for i, line in enumerate(lines):
            line_num = i + 1
            line_content = line.strip()
            
            # 跳过空行和注释
            if not line_content or line_content.startswith('//'):
                continue
            
            # 处理命名空间
            namespace_match = self.patterns['namespace'].match(line_content)
            if namespace_match:
                current_namespace = namespace_match.group(1)
                entities.append({
                    'type': 'namespace',
                    'name': current_namespace,
                    'file_path': relative_path,
                    'line_start': line_num,
                    'line_end': self._find_brace_end(lines, i),
                    'signature': line_content
                })
                continue
            
            # 处理类
            class_match = self.patterns['class'].match(line_content)
            if class_match:
                class_name = class_match.group(1)
                current_class = class_name
                end_line = self._find_brace_end(lines, i)
                entities.append({
                    'type': 'class',
                    'name': class_name,
                    'file_path': relative_path,
                    'line_start': line_num,
                    'line_end': end_line,
                    'namespace': current_namespace,
                    'signature': line_content,
                    'parent': self._extract_parent_class(line_content)
                })
                continue
            
            # 处理结构体
            struct_match = self.patterns['struct'].match(line_content)
            if struct_match:
                struct_name = struct_match.group(1)
                end_line = self._find_brace_end(lines, i)
                entities.append({
                    'type': 'struct',
                    'name': struct_name,
                    'file_path': relative_path,
                    'line_start': line_num,
                    'line_end': end_line,
                    'namespace': current_namespace,
                    'signature': line_content
                })
                continue
            
            # 处理枚举
            enum_match = self.patterns['enum'].match(line_content)
            if enum_match:
                enum_name = enum_match.group(1)
                end_line = self._find_semicolon_end(lines, i)
                entities.append({
                    'type': 'enum',
                    'name': enum_name,
                    'file_path': relative_path,
                    'line_start': line_num,
                    'line_end': end_line,
                    'signature': line_content
                })
                continue
            
            # 处理函数声明（包含多行）
            if '(' in line_content and ('{' in line_content or ';' in line_content):
                # 尝试合并多行
                full_signature = self._merge_multiline_signature(lines, i)
                
                # 检查是否是构造函数
                if self._is_constructor(full_signature, current_class):
                    func_name = self._extract_constructor_name(full_signature)
                    func_type = 'constructor'
                else:
                    func_match = self.patterns['function_declaration'].match(full_signature)
                    if func_match:
                        func_name = func_match.group(2)
                        func_type = 'function'
                    else:
                        # 尝试构造函数模式
                        constr_match = self.patterns['constructor'].match(full_signature)
                        if constr_match:
                            func_name = constr_match.group(1)
                            func_type = 'constructor' if func_name.startswith('~') else 'destructor'
                        else:
                            continue
                
                # 跳过操作符重载和特殊函数
                if func_name in ['operator', 'main', 'WINAPI', '__stdcall'] or \
                   'operator' in func_name or func_name.startswith('__'):
                    continue
                
                end_line = self._find_function_end(lines, i)
                
                # 提取返回类型和参数
                return_type, parameters = self._extract_function_info(full_signature)
                
                entities.append({
                    'type': func_type,
                    'name': func_name,
                    'file_path': relative_path,
                    'line_start': line_num,
                    'line_end': end_line,
                    'namespace': current_namespace,
                    'parent': current_class if current_class else None,
                    'signature': full_signature,
                    'return_type': return_type,
                    'parameters': parameters,
                    'is_template': 'template' in full_signature,
                    'is_virtual': 'virtual' in full_signature,
                    'is_static': 'static' in full_signature,
                    'is_const': 'const' in full_signature.split(')')[-1]
                })
        
        return entities
    
    def _find_brace_end(self, lines: List[str], start_index: int) -> int:
        """查找大括号结束的位置"""
        brace_count = 0
        in_scope = False
        
        for i in range(start_index, len(lines)):
            line = lines[i]
            brace_count += line.count('{')
            brace_count -= line.count('}')
            
            if brace_count > 0:
                in_scope = True
            elif in_scope and brace_count == 0:
                return i + 1
        
        return len(lines)
    
    def _find_semicolon_end(self, lines: List[str], start_index: int) -> int:
        """查找分号结束的位置"""
        for i in range(start_index, len(lines)):
            if ';' in lines[i]:
                return i + 1
        return len(lines)
    
    def _find_function_end(self, lines: List[str], start_index: int) -> int:
        """查找函数结束的位置"""
        # 检查是否有函数体
        for i in range(start_index, min(start_index + 10, len(lines))):
            if '{' in lines[i]:
                return self._find_brace_end(lines, i)
            elif ';' in lines[i]:
                return i + 1
        return start_index + 1
    
    def _merge_multiline_signature(self, lines: List[str], start_index: int) -> str:
        """合并多行函数签名"""
        signature_lines = []
        brace_count = 0
        parenthesis_count = 0
        found_semicolon = False
        
        for i in range(start_index, min(start_index + 10, len(lines))):
            line = lines[i].strip()
            signature_lines.append(line)
            
            # 统计括号
            parenthesis_count += line.count('(') - line.count(')')
            
            # 如果有函数体开始
            if '{' in line:
                brace_count += 1
            
            # 如果有分号并且括号匹配
            if ';' in line and parenthesis_count == 0 and brace_count == 0:
                found_semicolon = True
                break
            
            # 如果有函数体并且括号匹配
            if '{' in line and parenthesis_count == 0:
                break
        
        return ' '.join(signature_lines)
    
    def _extract_parent_class(self, signature: str) -> str:
        """从类签名中提取父类"""
        if ':' in signature:
            parts = signature.split(':')
            if len(parts) > 1:
                inheritance_part = parts[1].strip()
                # 提取第一个父类
                for word in inheritance_part.split():
                    if word not in ['public', 'private', 'protected', 'virtual']:
                        return word.split(',')[0].split('<')[0]
        return ""
    
    def _is_constructor(self, signature: str, current_class: str) -> bool:
        """判断是否为构造函数"""
        # 检查是否是构造函数（与类同名）或析构函数（以~开头）
        if current_class:
            # 去除模板参数
            clean_class = current_class.split('<')[0]
            if clean_class + '(' in signature:
                return True
            if '~' + clean_class + '(' in signature:
                return True
        return False
    
    def _extract_constructor_name(self, signature: str) -> str:
        """提取构造函数名"""
        # 查找第一个单词（可能是~表示析构函数）
        match = re.search(r'(\~?\w+)\(', signature)
        return match.group(1) if match else ""
    
    def _extract_function_info(self, signature: str) -> Tuple[str, List[Dict[str, str]]]:
        """提取函数返回类型和参数信息"""
        # 提取返回类型
        return_type = ""
        param_part = ""
        
        # 找到函数名和参数部分
        match = re.search(r'(\w+(?:<[^>]+>)?(?:\s*[*&]+)?\s+)?(\w+)\s*\(([^)]*)\)', signature)
        if match:
            return_type = match.group(1).strip() if match.group(1) else ""
            param_str = match.group(3)
            
            # 提取参数
            parameters = []
            if param_str.strip():
                # 分割参数，但要注意模板参数中的逗号
                param_list = self._split_parameters(param_str)
                
                for param in param_list:
                    param = param.strip()
                    if param:
                        # 解析参数类型和名称
                        param_match = re.match(r'(\w+(?:<[^>]+>)?(?:\s*[*&]+)?)\s+(\w+)', param)
                        if param_match:
                            param_type = param_match.group(1).strip()
                            param_name = param_match.group(2).strip()
                            parameters.append({'name': param_name, 'type': param_type})
                        elif '...' in param:  # 可变参数
                            parameters.append({'name': '...', 'type': 'variadic'})
                        else:  # 只有类型没有名称
                            parameters.append({'name': '', 'type': param.strip()})
        
        return return_type, parameters
    
    def _split_parameters(self, param_str: str) -> List[str]:
        """分割参数字符串，正确处理模板参数"""
        params = []
        current_param = ""
        template_depth = 0
        bracket_depth = 0
        
        for char in param_str:
            if char == '<':
                template_depth += 1
            elif char == '>':
                template_depth -= 1
            elif char == '[':
                bracket_depth += 1
            elif char == ']':
                bracket_depth -= 1
            elif char == ',' and template_depth == 0 and bracket_depth == 0:
                params.append(current_param.strip())
                current_param = ""
                continue
            
            current_param += char
        
        if current_param.strip():
            params.append(current_param.strip())
        
        return params
    
    def get_entity_statistics(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取实体统计信息"""
        type_counts = {}
        for entity in entities:
            entity_type = entity['type']
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1
        
        return type_counts


class HybridCppCodeParser:
    """混合C++代码解析器 - 结合多种方法提高准确性"""
    
    def __init__(self, codebase_path: str):
        self.codebase_path = Path(codebase_path)
        
        # 尝试使用高级解析器
        try:
            self.parser = AdvancedCppCodeParser(codebase_path)
        except Exception as e:
            logger.warning(f"高级解析器初始化失败: {e}")
            self.parser = None
        
        # 简单的正则解析器作为后备
        self.simple_parser = SimpleCppCodeParser(codebase_path)
    
    def parse_codebase_entities(self) -> List[Dict[str, Any]]:
        """解析代码库实体"""
        if self.parser and self.parser.use_clang:
            logger.info("使用高级解析器（libclang）")
            return self.parser.parse_codebase_entities()
        elif self.parser:
            logger.info("使用高级解析器（正则）")
            return self.parser.parse_codebase_entities()
        else:
            logger.info("使用简单解析器")
            return self.simple_parser.parse_codebase_entities()
    
    def get_entity_statistics(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取实体统计信息"""
        return self.simple_parser.get_entity_statistics(entities)


class SimpleCppCodeParser:
    """简单C++代码解析器 - 用于测试"""
    
    def __init__(self, codebase_path: str):
        self.codebase_path = Path(codebase_path)
        self.supported_extensions = {'.cpp', '.cc', '.cxx', '.c', '.h', '.hpp', '.hxx', '.hh'}
    
    def parse_codebase_entities(self) -> List[Dict[str, Any]]:
        """解析代码库实体 - 简化版本"""
        logger.info("使用简单解析器解析代码结构...")
        
        all_entities = []
        
        for file_path in self.codebase_path.rglob('*'):
            if self._is_cpp_file(file_path):
                try:
                    entities = self._parse_file_simple(file_path)
                    all_entities.extend(entities)
                except Exception as e:
                    logger.error(f"解析文件 {file_path} 失败: {e}")
        
        logger.info(f"✓ 解析完成: {len(all_entities)} 个实体")
        return all_entities
    
    def _is_cpp_file(self, file_path: Path) -> bool:
        """判断是否为C++文件"""
        return file_path.is_file() and file_path.suffix.lower() in self.supported_extensions
    
    def _parse_file_simple(self, file_path: Path) -> List[Dict[str, Any]]:
        """简单解析文件"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        entities = []
        relative_path = str(file_path.relative_to(self.codebase_path))
        lines = content.split('\n')
        
        # 添加文件实体
        entities.append({
            'type': 'file',
            'name': file_path.name,
            'file_path': relative_path,
            'line_start': 1,
            'line_end': len(lines)
        })
        
        # 简单的模式匹配
        patterns = [
            (r'^\s*class\s+(\w+)', 'class'),
            (r'^\s*struct\s+(\w+)', 'struct'),
            (r'^\s*namespace\s+(\w+)', 'namespace'),
            (r'^\s*(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{', 'function'),
            (r'^\s*(\~?\w+)\s*\([^)]*\)\s*\{', 'constructor'),
            (r'^\s*enum(?:\s+class)?\s+(\w+)', 'enum'),
        ]
        
        for i, line in enumerate(lines):
            line_content = line.strip()
            
            for pattern, entity_type in patterns:
                match = re.search(pattern, line_content)
                if match:
                    name = match.group(1)
                    # 过滤掉常见关键字
                    if name not in ['if', 'else', 'for', 'while', 'do', 'switch', 'case', 'return']:
                        entities.append({
                            'type': entity_type,
                            'name': name,
                            'file_path': relative_path,
                            'line_start': i + 1,
                            'line_end': i + 1,
                            'signature': line_content[:100]  # 限制长度
                        })
                    break
        
        return entities
    
    def get_entity_statistics(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取实体统计信息"""
        type_counts = {}
        for entity in entities:
            entity_type = entity['type']
            type_counts[entity_type] = type_counts.get(entity_type, 0) + 1
        
        return type_counts

from clang.cindex import Cursor, CursorKind, TokenKind
from typing import Dict, List, Set, Tuple, Optional

class CppCallGraphAnalyzer:
    """
    企业级C++调用关系图分析器
    基于Clang AST进行精确的调用关系提取
    """
    
    def __init__(self, codebase_path: str):
        self.codebase_path = Path(codebase_path)
        # 存储函数签名到节点的映射（用于快速查找）
        self.function_signature_map: Dict[str, Dict] = {}
        # 存储解析结果：caller -> [(callee, call_location, call_type)]
        self.call_relationships: Dict[str, List[Tuple[str, str, str]]] = {}
        
    def build_signature_map(self, functions: List[Dict[str, Any]]):
        """
        构建函数签名映射，用于快速查找被调用函数
        
        关键：为每个函数生成唯一签名，考虑命名空间、类名、参数类型
        """
        for func in functions:
            # 生成标准化函数签名
            signature = self._generate_function_signature(func)
            self.function_signature_map[signature] = func
            
            # 同时存储简化的名称映射（用于容错匹配）
            simple_name = func['name']
            if simple_name not in self.function_signature_map:
                self.function_signature_map[simple_name] = func
    
    def _generate_function_signature(self, func: Dict[str, Any]) -> str:
        """
        生成唯一函数签名
        格式：Namespace::ClassName::FunctionName(ParamType1,ParamType2)
        """
        parts = []
        
        # 添加命名空间
        if func.get('namespace'):
            parts.append(func['namespace'])
        
        # 添加父类（如果是成员函数）
        if func.get('parent'):
            parts.append(func['parent'])
        
        # 添加函数名
        parts.append(func['name'])
        
        # 构建基础签名
        base_sig = '::'.join(parts)
        
        # 添加参数类型（关键区别）
        param_types = []
        for param in func.get('parameters', []):
            # 简化参数类型，移除空格和修饰符
            param_type = param.get('type', '').replace(' ', '').replace('*', '_ptr').replace('&', '_ref')
            param_types.append(param_type)
        
        param_sig = ','.join(param_types) if param_types else 'void'
        return f"{base_sig}({param_sig})"
    
    def analyze_function_calls(self, file_path: Path, functions_in_file: List[Dict[str, Any]]):
        """
        分析单个文件中的函数调用关系
        """
        # 使用clang解析文件
        index = clang.cindex.Index.create()
        translation_unit = index.parse(str(file_path))
        
        # 遍历AST
        for node in translation_unit.cursor.walk_preorder():
            self._process_cursor_for_calls(node, str(file_path))
    
    def _process_cursor_for_calls(self, cursor: Cursor, file_path: str):
        """
        处理AST节点，提取调用关系
        """
        # 只处理函数定义内部的调用
        if cursor.kind == CursorKind.FUNCTION_DECL or cursor.kind == CursorKind.CXX_METHOD:
            if cursor.is_definition():  # 只处理函数定义，不是声明
                caller_signature = self._cursor_to_signature(cursor)
                
                # 遍历函数体内的所有调用
                for child in cursor.walk_preorder():
                    self._extract_calls_from_cursor(child, caller_signature, file_path)
    
    def _extract_calls_from_cursor(self, cursor: Cursor, caller_sig: str, file_path: str):
        """
        从光标中提取调用表达式
        """
        call_type = "direct"
        
        # 1. 直接函数调用
        if cursor.kind == CursorKind.CALL_EXPR:
            called_func = self._resolve_called_function(cursor, file_path)
            if called_func:
                self._add_call_relationship(caller_sig, called_func, file_path, call_type)
        
        # 2. 成员函数调用（包括虚函数）
        elif cursor.kind == CursorKind.CXX_MEMBER_CALL_EXPR:
            call_type = "member"
            called_func = self._resolve_member_call(cursor, file_path)
            if called_func:
                self._add_call_relationship(caller_sig, called_func, file_path, call_type)
        
        # 3. 运算符调用
        elif cursor.kind == CursorKind.CXX_OPERATOR_CALL_EXPR:
            call_type = "operator"
            called_func = self._resolve_operator_call(cursor, file_path)
            if called_func:
                self._add_call_relationship(caller_sig, called_func, file_path, call_type)
        
        # 4. 模板函数调用
        elif cursor.kind == CursorKind.TEMPLATE_REF:
            call_type = "template"
            called_func = self._resolve_template_call(cursor, file_path)
            if called_func:
                self._add_call_relationship(caller_sig, called_func, file_path, call_type)
    
    def _resolve_called_function(self, cursor: Cursor, file_path: str) -> Optional[str]:
        """
        解析被调用函数的签名
        """
        try:
            # 获取被调用函数的引用
            called_cursor = cursor.referenced
            if called_cursor:
                return self._cursor_to_signature(called_cursor)
            
            # 如果无法直接获取引用，尝试从表达式文本中提取
            call_text = self._get_cursor_text(cursor).split('(')[0].strip()
            return self._find_function_by_name(call_text)
            
        except Exception as e:
            logger.debug(f"解析被调用函数失败: {e}")
            return None
    
    def _resolve_member_call(self, cursor: Cursor, file_path: str) -> Optional[str]:
        """
        解析成员函数调用（特别处理虚函数）
        """
        try:
            # 获取成员函数
            member_cursor = cursor.referenced
            if member_cursor:
                signature = self._cursor_to_signature(member_cursor)
                
                # 检查是否为虚函数
                if member_cursor.is_virtual_method():
                    # 对于虚函数，需要找到所有可能的重写
                    base_signature = signature
                    possible_callees = self._find_virtual_overrides(base_signature)
                    if possible_callees:
                        # 返回第一个找到的重写，实际应用中可能需要记录所有可能性
                        return possible_callees[0]
                
                return signature
        except Exception as e:
            logger.debug(f"解析成员调用失败: {e}")
        return None
    
    def _cursor_to_signature(self, cursor: Cursor) -> str:
        """
        将Clang光标转换为标准化的函数签名
        """
        # 获取函数名
        func_name = cursor.spelling or cursor.displayname
        
        # 获取参数类型
        param_types = []
        if cursor.kind in [CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD]:
            for arg in cursor.get_arguments():
                param_types.append(arg.type.spelling)
        
        # 获取返回类型
        return_type = cursor.result_type.spelling if hasattr(cursor, 'result_type') else ""
        
        # 获取父类和命名空间
        namespace_parts = []
        parent_cursor = cursor.semantic_parent
        
        while parent_cursor:
            if parent_cursor.kind == CursorKind.NAMESPACE:
                namespace_parts.insert(0, parent_cursor.spelling)
            elif parent_cursor.kind in [CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL]:
                namespace_parts.insert(0, parent_cursor.spelling)
            parent_cursor = parent_cursor.semantic_parent
        
        # 构建完整签名
        base_name = '::'.join(namespace_parts + [func_name])
        param_sig = ','.join(param_types) if param_types else 'void'
        
        return f"{base_name}({param_sig})"
    
    def _add_call_relationship(self, caller: str, callee: str, location: str, call_type: str):
        """添加调用关系到存储结构"""
        if caller not in self.call_relationships:
            self.call_relationships[caller] = []
        
        # 避免重复添加相同的调用关系
        existing = [rel for rel in self.call_relationships[caller] 
                   if rel[0] == callee and rel[1] == location]
        
        if not existing:
            self.call_relationships[caller].append((callee, location, call_type))
            logger.debug(f"发现调用: {caller} -> {callee} ({call_type})")
    
    def get_call_graph(self) -> Dict[str, List[Tuple[str, str, str]]]:
        """获取完整的调用关系图"""
        return self.call_relationships
    
    def export_to_neo4j(self, function_nodes: Dict[str, Any]):
        """
        将调用关系导出到Neo4j（替换你原来的_infer_call_relationships）
        """
        logger.info("导出调用关系到Neo4j...")
        created_count = 0
        
        for caller_sig, calls in self.call_relationships.items():
            # 查找调用者节点
            caller_node = self._find_node_by_signature(caller_sig, function_nodes)
            if not caller_node:
                continue
            
            for callee_sig, location, call_type in calls:
                # 查找被调用者节点
                callee_node = self._find_node_by_signature(callee_sig, function_nodes)
                if not callee_node:
                    continue
                
                # 创建关系（使用你的_merge_relationship方法）
                success = self._merge_relationship(
                    caller_node,
                    "CALLS",
                    callee_node,
                    {
                        "inferred": False,  # 这是实际分析得到的，不是推断的
                        "location": location,
                        "call_type": call_type,
                        "confidence": 1.0    # 实际分析，置信度最高
                    }
                )
                
                if success:
                    created_count += 1
        
        logger.info(f"创建/更新了 {created_count} 个调用关系（基于AST分析）")