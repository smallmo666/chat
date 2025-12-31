import pandas as pd
from typing import Dict, Any, List, Optional

class VisualizationAdvisor:
    """
    基于数据特征推荐最佳可视化图表类型。
    """
    
    def analyze_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析数据特征并推荐图表。
        """
        if not data:
            return {"recommended_chart": "none", "reason": "无数据"}
            
        df = pd.DataFrame(data)
        
        # 1. 识别列类型
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        datetime_cols = []
        category_cols = []
        
        for col in df.select_dtypes(include=['object', 'string']).columns:
            # 尝试转换为时间
            try:
                pd.to_datetime(df[col], errors='raise')
                datetime_cols.append(col)
            except:
                category_cols.append(col)
                
        # 2. 规则推荐
        recommendation = "table"
        reason = "默认展示表格"
        x_axis = None
        y_axis = None
        
        # 规则 1: 趋势分析 (时间序列)
        if datetime_cols and numeric_cols:
            recommendation = "line"
            if len(numeric_cols) > 1:
                reason = f"检测到时间列 '{datetime_cols[0]}' 和多个数值列 ({', '.join(numeric_cols)})，适合展示多维趋势对比。"
            else:
                reason = f"检测到时间列 '{datetime_cols[0]}' 和数值列，适合展示趋势。"
            x_axis = datetime_cols[0]
            y_axis = numeric_cols
            
        # 规则 2: 类别比较 (柱状图)
        elif category_cols and numeric_cols:
            # 如果类别太多，不适合柱状图，可能适合条形图
            unique_count = df[category_cols[0]].nunique()
            if unique_count <= 20:
                recommendation = "bar"
                if len(numeric_cols) > 1:
                    reason = f"检测到类别列 '{category_cols[0]}' 和多个数值列 ({', '.join(numeric_cols)})，适合进行分组对比。"
                else:
                    reason = f"检测到类别列 '{category_cols[0]}' (基数={unique_count})，适合对比。"
                x_axis = category_cols[0]
                y_axis = numeric_cols
            else:
                recommendation = "table"
                reason = "类别过多，建议表格展示。"
                
        # 规则 3: 占比分析 (饼图)
        # 仅当只有1个类别列和1个数值列，且行数较少时
        if len(category_cols) == 1 and len(numeric_cols) == 1 and len(df) <= 8:
            recommendation = "pie"
            reason = "数据量少且包含单一类别与数值，适合饼图。"
            x_axis = category_cols[0]
            y_axis = numeric_cols
            
        return {
            "recommended_chart": recommendation,
            "reason": reason,
            "x_axis": x_axis,
            "y_axis": y_axis,
            "columns": {
                "numeric": numeric_cols,
                "datetime": datetime_cols,
                "category": category_cols
            }
        }

# 全局实例
_advisor = VisualizationAdvisor()

def get_viz_advisor():
    return _advisor
