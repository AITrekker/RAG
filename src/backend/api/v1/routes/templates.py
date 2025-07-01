"""
Template Management API Routes

Provides endpoints for managing prompt templates including hot-reloading.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List
from src.backend.config.rag_prompts import rag_prompts
from src.backend.dependencies import get_current_tenant_dep
from src.backend.models.database import Tenant

router = APIRouter(prefix="/templates", tags=["templates"])

@router.get("/")
async def list_templates(
    current_tenant: Tenant = Depends(get_current_tenant_dep)
) -> Dict[str, Any]:
    """List all available prompt templates"""
    try:
        templates = rag_prompts.get_available_templates()
        
        return {
            "templates": templates,
            "current_default": rag_prompts.get_current_template(),
            "total_count": len(templates)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list templates: {str(e)}"
        )

@router.get("/{template_name}")
async def get_template(
    template_name: str,
    current_tenant: Tenant = Depends(get_current_tenant_dep)
) -> Dict[str, Any]:
    """Get a specific prompt template"""
    try:
        # This will check for hot-reload automatically
        template_content = rag_prompts.get_prompt_template(template_name)
        available_templates = rag_prompts.get_available_templates()
        
        if template_name not in available_templates:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template '{template_name}' not found"
            )
        
        return {
            "template_name": template_name,
            "description": available_templates[template_name],
            "content": template_content,
            "is_external": template_name in rag_prompts._loaded_templates
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get template: {str(e)}"
        )

@router.post("/reload")
async def reload_templates(
    current_tenant: Tenant = Depends(get_current_tenant_dep)
) -> Dict[str, Any]:
    """Manually reload all prompt templates from config files"""
    try:
        # Get status before reload
        old_count = len(rag_prompts._loaded_templates)
        
        # Force reload
        rag_prompts.force_reload()
        
        # Get status after reload
        new_count = len(rag_prompts._loaded_templates)
        
        return {
            "message": "Templates reloaded successfully",
            "old_template_count": old_count,
            "new_template_count": new_count,
            "templates_changed": new_count != old_count,
            "loaded_templates": list(rag_prompts._loaded_templates.keys())
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload templates: {str(e)}"
        )

@router.get("/status/reload")
async def get_reload_status(
    current_tenant: Tenant = Depends(get_current_tenant_dep)
) -> Dict[str, Any]:
    """Get hot-reload status and configuration"""
    try:
        status = rag_prompts.get_reload_status()
        return {
            "reload_status": status,
            "message": "Hot-reload is enabled" if status["hot_reload_enabled"] else "Hot-reload is disabled"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get reload status: {str(e)}"
        )

@router.post("/status/reload/enable")
async def enable_hot_reload(
    current_tenant: Tenant = Depends(get_current_tenant_dep)
) -> Dict[str, str]:
    """Enable hot-reloading of prompt templates"""
    try:
        rag_prompts.enable_hot_reload()
        return {"message": "Hot-reload enabled successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable hot-reload: {str(e)}"
        )

@router.post("/status/reload/disable") 
async def disable_hot_reload(
    current_tenant: Tenant = Depends(get_current_tenant_dep)
) -> Dict[str, str]:
    """Disable hot-reloading of prompt templates"""
    try:
        rag_prompts.disable_hot_reload()
        return {"message": "Hot-reload disabled successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable hot-reload: {str(e)}"
        )

@router.post("/validate/{template_name}")
async def validate_template(
    template_name: str,
    current_tenant: Tenant = Depends(get_current_tenant_dep)
) -> Dict[str, Any]:
    """Validate a prompt template by testing it with sample data"""
    try:
        template_content = rag_prompts.get_prompt_template(template_name)
        
        # Test template with sample data
        sample_query = "What is the company's mission?"
        sample_context = "[Source 1 - company_overview.txt]: Our company mission is to provide excellent service."
        
        try:
            formatted_prompt = template_content.format(
                query=sample_query,
                context=sample_context
            )
            
            return {
                "template_name": template_name,
                "is_valid": True,
                "message": "Template is valid and can be formatted correctly",
                "sample_output_length": len(formatted_prompt),
                "sample_preview": formatted_prompt[:200] + "..." if len(formatted_prompt) > 200 else formatted_prompt
            }
            
        except Exception as format_error:
            return {
                "template_name": template_name,
                "is_valid": False,
                "message": f"Template formatting failed: {str(format_error)}",
                "error_type": "formatting_error"
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate template: {str(e)}"
        )