import React, { useState, useEffect } from 'react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'
import { useToast } from '../../hooks/useToast'

interface ApiSettings {
  gemini_api_key: string
  rag_enabled: boolean
}

export function SettingsView() {
  const [settings, setSettings] = useState<ApiSettings>({
    gemini_api_key: '',
    rag_enabled: false
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  const { toast } = useToast()

  // Load current settings
  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/system/settings')
      if (response.ok) {
        const data = await response.json()
        setSettings({
          gemini_api_key: data.gemini_api_key || '',
          rag_enabled: data.rag_enabled || false
        })
      } else {
        throw new Error('Failed to load settings')
      }
    } catch (error) {
      console.error('Failed to load settings:', error)
      toast({
        title: "加载失败",
        description: "无法加载系统设置",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const saveSettings = async () => {
    try {
      setSaving(true)
      const response = await fetch('/api/system/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      })

      if (response.ok) {
        toast({
          title: "设置已保存",
          description: "系统设置已成功更新",
          variant: "default"
        })
      } else {
        throw new Error('Failed to save settings')
      }
    } catch (error) {
      console.error('Failed to save settings:', error)
      toast({
        title: "保存失败",
        description: "无法保存系统设置",
        variant: "destructive"
      })
    } finally {
      setSaving(false)
    }
  }

  const testApiKey = async () => {
    if (!settings.gemini_api_key.trim()) {
      toast({
        title: "API密钥为空",
        description: "请先输入Gemini API密钥",
        variant: "destructive"
      })
      return
    }

    try {
      setLoading(true)
      const response = await fetch('/api/system/test-api-key', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ api_key: settings.gemini_api_key })
      })

      const result = await response.json()
      
      if (response.ok && result.valid) {
        toast({
          title: "API密钥有效",
          description: "Gemini API密钥测试成功",
          variant: "default"
        })
      } else {
        toast({
          title: "API密钥无效",
          description: result.error || "API密钥测试失败",
          variant: "destructive"
        })
      }
    } catch (error) {
      console.error('Failed to test API key:', error)
      toast({
        title: "测试失败",
        description: "无法测试API密钥",
        variant: "destructive"
      })
    } finally {
      setLoading(false)
    }
  }

  const maskApiKey = (key: string) => {
    if (!key || key.length < 8) return key
    return key.substring(0, 4) + '●●●●●●●●' + key.substring(key.length - 4)
  }

  if (loading && !settings.gemini_api_key) {
    return (
      <div className="flex items-center justify-center min-h-96">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">加载设置中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-8">
      <div className="border-b border-gray-200 dark:border-gray-700 pb-4">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">系统设置</h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          配置API密钥和系统参数
        </p>
      </div>

      {/* API Configuration Section */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          AI服务配置
        </h2>
        
        <div className="space-y-6">
          {/* Gemini API Key */}
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Google Gemini API密钥
            </label>
            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  type={showApiKey ? "text" : "password"}
                  value={showApiKey ? settings.gemini_api_key : maskApiKey(settings.gemini_api_key)}
                  onChange={(e) => setSettings(prev => ({ 
                    ...prev, 
                    gemini_api_key: e.target.value 
                  }))}
                  placeholder="输入您的Gemini API密钥"
                  className="w-full"
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowApiKey(!showApiKey)}
                className="px-3"
              >
                {showApiKey ? '隐藏' : '显示'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={testApiKey}
                disabled={loading || !settings.gemini_api_key.trim()}
                className="px-4"
              >
                {loading ? '测试中...' : '测试'}
              </Button>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
              API密钥用于启用RAG智能问答功能。
              <a 
                href="https://makersuite.google.com/app/apikey" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-500 ml-1"
              >
                获取API密钥 →
              </a>
            </p>
          </div>

          {/* RAG Enable Toggle */}
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                启用RAG智能问答
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                启用后可以对文档进行智能问答查询
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSettings(prev => ({ 
                ...prev, 
                rag_enabled: !prev.rag_enabled 
              }))}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
                settings.rag_enabled 
                  ? 'bg-blue-600' 
                  : 'bg-gray-200 dark:bg-gray-700'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  settings.rag_enabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* System Status Section */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          系统状态
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <div className={`w-3 h-3 rounded-full mx-auto mb-2 ${
              settings.gemini_api_key ? 'bg-green-500' : 'bg-red-500'
            }`}></div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">API密钥</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {settings.gemini_api_key ? '已配置' : '未配置'}
            </p>
          </div>
          
          <div className="text-center p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <div className={`w-3 h-3 rounded-full mx-auto mb-2 ${
              settings.rag_enabled ? 'bg-green-500' : 'bg-yellow-500'
            }`}></div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">RAG功能</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {settings.rag_enabled ? '已启用' : '已禁用'}
            </p>
          </div>
          
          <div className="text-center p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <div className="w-3 h-3 bg-green-500 rounded-full mx-auto mb-2"></div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">数据库</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">正常</p>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end gap-4">
        <Button
          variant="outline"
          onClick={loadSettings}
          disabled={loading || saving}
        >
          重置
        </Button>
        <Button
          onClick={saveSettings}
          disabled={saving}
          className="px-8"
        >
          {saving ? '保存中...' : '保存设置'}
        </Button>
      </div>
    </div>
  )
}