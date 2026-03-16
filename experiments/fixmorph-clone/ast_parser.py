#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import javalang
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class CodeSegment:
    """Represents a Java code segment (class, method, field, enum)"""
    segment_type: str  # 'class', 'method', 'field', 'enum', 'interface'
    name: str
    signature: str
    start_line: int
    end_line: int
    file_path: str
    parent_class: Optional[str] = None
    modifiers: List[str] = field(default_factory=list)
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    body_hash: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'segment_type': self.segment_type,
            'name': self.name,
            'signature': self.signature,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'file_path': self.file_path,
            'parent_class': self.parent_class,
            'modifiers': self.modifiers,
            'parameters': self.parameters,
            'return_type': self.return_type
        }


class JavaASTParser:
    """Parser for Java source files using javalang"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.source_code = None
        self.tree = None
        self.lines = []
        
    def parse(self) -> bool:
        """Parse the Java file and build AST"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.source_code = f.read()
                self.lines = self.source_code.split('\n')
            
            self.tree = javalang.parse.parse(self.source_code)
            return True
        except Exception as e:
            print(f"Error parsing {self.file_path}: {e}")
            return False
    
    def extract_classes(self) -> List[CodeSegment]:
        """Extract all class declarations"""
        segments = []
        
        for path, node in self.tree.filter(javalang.tree.ClassDeclaration):
            start_line = node.position.line if node.position else 0
            end_line = self._find_end_line(start_line, 'class')
            
            segment = CodeSegment(
                segment_type='class',
                name=node.name,
                signature=self._generate_class_signature(node),
                start_line=start_line,
                end_line=end_line,
                file_path=self.file_path,
                modifiers=node.modifiers if node.modifiers else []
            )
            segments.append(segment)
        
        return segments
    
    def extract_interfaces(self) -> List[CodeSegment]:
        """Extract all interface declarations"""
        segments = []
        
        for path, node in self.tree.filter(javalang.tree.InterfaceDeclaration):
            start_line = node.position.line if node.position else 0
            end_line = self._find_end_line(start_line, 'interface')
            
            segment = CodeSegment(
                segment_type='interface',
                name=node.name,
                signature=self._generate_interface_signature(node),
                start_line=start_line,
                end_line=end_line,
                file_path=self.file_path,
                modifiers=node.modifiers if node.modifiers else []
            )
            segments.append(segment)
        
        return segments
    
    def extract_enums(self) -> List[CodeSegment]:
        """Extract all enum declarations"""
        segments = []
        
        for path, node in self.tree.filter(javalang.tree.EnumDeclaration):
            start_line = node.position.line if node.position else 0
            end_line = self._find_end_line(start_line, 'enum')
            
            segment = CodeSegment(
                segment_type='enum',
                name=node.name,
                signature=f"enum {node.name}",
                start_line=start_line,
                end_line=end_line,
                file_path=self.file_path,
                modifiers=node.modifiers if node.modifiers else []
            )
            segments.append(segment)
        
        return segments
    
    def extract_methods(self) -> List[CodeSegment]:
        """Extract all method declarations"""
        segments = []
        
        for path, node in self.tree.filter(javalang.tree.MethodDeclaration):
            parent_class = self._find_parent_class(path)
            start_line = node.position.line if node.position else 0
            end_line = self._find_end_line(start_line, 'method')
            
            params = []
            if node.parameters:
                params = [f"{p.type.name} {p.name}" for p in node.parameters]
            
            return_type = node.return_type.name if node.return_type else 'void'
            
            segment = CodeSegment(
                segment_type='method',
                name=node.name,
                signature=self._generate_method_signature(node),
                start_line=start_line,
                end_line=end_line,
                file_path=self.file_path,
                parent_class=parent_class,
                modifiers=node.modifiers if node.modifiers else [],
                parameters=params,
                return_type=return_type,
                body_hash=hash(str(node.body)) if node.body else None
            )
            segments.append(segment)
        
        return segments
    
    def extract_constructors(self) -> List[CodeSegment]:
        """Extract all constructor declarations"""
        segments = []
        
        for path, node in self.tree.filter(javalang.tree.ConstructorDeclaration):
            parent_class = self._find_parent_class(path)
            start_line = node.position.line if node.position else 0
            end_line = self._find_end_line(start_line, 'constructor')
            
            params = []
            if node.parameters:
                params = [f"{p.type.name} {p.name}" for p in node.parameters]
            
            segment = CodeSegment(
                segment_type='method',  # Treat as method for consistency
                name=node.name,
                signature=self._generate_constructor_signature(node),
                start_line=start_line,
                end_line=end_line,
                file_path=self.file_path,
                parent_class=parent_class,
                modifiers=node.modifiers if node.modifiers else [],
                parameters=params,
                return_type=None,
                body_hash=hash(str(node.body)) if node.body else None
            )
            segments.append(segment)
        
        return segments
    
    def extract_fields(self) -> List[CodeSegment]:
        """Extract all field declarations"""
        segments = []
        
        for path, node in self.tree.filter(javalang.tree.FieldDeclaration):
            parent_class = self._find_parent_class(path)
            start_line = node.position.line if node.position else 0
            
            for declarator in node.declarators:
                segment = CodeSegment(
                    segment_type='field',
                    name=declarator.name,
                    signature=self._generate_field_signature(node, declarator),
                    start_line=start_line,
                    end_line=start_line,  # Fields typically on one line
                    file_path=self.file_path,
                    parent_class=parent_class,
                    modifiers=node.modifiers if node.modifiers else [],
                    return_type=node.type.name if hasattr(node.type, 'name') else str(node.type)
                )
                segments.append(segment)
        
        return segments
    
    def extract_all_segments(self) -> Dict[str, List[CodeSegment]]:
        """Extract all code segments from the file"""
        if not self.tree:
            self.parse()
        
        return {
            'classes': self.extract_classes(),
            'interfaces': self.extract_interfaces(),
            'enums': self.extract_enums(),
            'methods': self.extract_methods() + self.extract_constructors(),
            'fields': self.extract_fields()
        }
    
    def _find_parent_class(self, path) -> Optional[str]:
        """Find the parent class name from the AST path"""
        for node in reversed(path):
            if isinstance(node, (javalang.tree.ClassDeclaration, 
                               javalang.tree.InterfaceDeclaration)):
                return node.name
        return None
    
    def _find_end_line(self, start_line: int, node_type: str) -> int:
        """Find the end line of a code block by counting braces"""
        if start_line <= 0 or start_line > len(self.lines):
            return start_line
        
        brace_count = 0
        in_block = False
        
        for i in range(start_line - 1, len(self.lines)):
            line = self.lines[i]
            
            for char in line:
                if char == '{':
                    brace_count += 1
                    in_block = True
                elif char == '}':
                    brace_count -= 1
                    if in_block and brace_count == 0:
                        return i + 1
        
        return start_line
    
    def _generate_class_signature(self, node) -> str:
        """Generate signature for class"""
        mods = ' '.join(node.modifiers) if node.modifiers else ''
        extends = f" extends {node.extends.name}" if node.extends else ''
        implements = ''
        if node.implements:
            impl_names = [impl.name for impl in node.implements]
            implements = f" implements {', '.join(impl_names)}"
        
        return f"{mods} class {node.name}{extends}{implements}".strip()
    
    def _generate_interface_signature(self, node) -> str:
        """Generate signature for interface"""
        mods = ' '.join(node.modifiers) if node.modifiers else ''
        extends = ''
        if node.extends:
            ext_names = [ext.name for ext in node.extends]
            extends = f" extends {', '.join(ext_names)}"
        
        return f"{mods} interface {node.name}{extends}".strip()
    
    def _generate_method_signature(self, node) -> str:
        """Generate signature for method"""
        mods = ' '.join(node.modifiers) if node.modifiers else ''
        return_type = node.return_type.name if node.return_type else 'void'
        params = []
        if node.parameters:
            params = [p.type.name for p in node.parameters]
        
        param_str = ', '.join(params)
        return f"{mods} {return_type} {node.name}({param_str})".strip()
    
    def _generate_constructor_signature(self, node) -> str:
        """Generate signature for constructor"""
        mods = ' '.join(node.modifiers) if node.modifiers else ''
        params = []
        if node.parameters:
            params = [p.type.name for p in node.parameters]
        
        param_str = ', '.join(params)
        return f"{mods} {node.name}({param_str})".strip()
    
    def _generate_field_signature(self, node, declarator) -> str:
        """Generate signature for field"""
        mods = ' '.join(node.modifiers) if node.modifiers else ''
        field_type = node.type.name if hasattr(node.type, 'name') else str(node.type)
        return f"{mods} {field_type} {declarator.name}".strip()