'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Upload, FileText, Check, X } from 'lucide-react';
import { uploadReport } from '@/services/api';

export default function UploadPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [companyName, setCompanyName] = useState('');
  const [market, setMarket] = useState<'CN' | 'HK' | 'US'>('US');
  const [symbol, setSymbol] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError('');
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('请选择文件');
      return;
    }
    // 公司名称可选，如果未填写则使用"待识别"

    setUploading(true);
    setError('');

    try {
      // 如果未填写公司名称，使用"待识别"
      const finalCompanyName = companyName.trim() || '待识别';
      // 报告期间自动设置为当前日期
      const today = new Date().toISOString().split('T')[0];
      await uploadReport(file, finalCompanyName, 'annual', today, market, symbol);
      router.push('/reports');
    } catch (err) {
      setError('上传失败，请重试');
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-5 md:p-8 flex flex-col gap-6 max-w-2xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-[#FAFAF9] text-xl md:text-2xl font-semibold">上传财务报表</h1>
        <p className="text-[#6B6B70] text-sm mt-1">支持PDF、Excel格式的财务报表文件</p>
      </div>

      {/* Upload Area */}
      <div 
        className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E] cursor-pointer"
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.xls,.xlsx"
          onChange={handleFileSelect}
          className="hidden"
        />
        <div className="border-2 border-dashed border-[#2A2A2E] rounded-xl p-10 text-center">
          <div className="w-20 h-20 mx-auto mb-5 bg-[#1A1A1E] rounded-2xl flex items-center justify-center">
            <Upload size={40} className="text-[#6B6B70]" />
          </div>
          <p className="text-[#FAFAF9] text-lg font-medium mb-2">点击或拖拽文件到此处</p>
          <p className="text-[#6B6B70] text-sm">支持 PDF、XLS、XLSX 格式</p>
        </div>
      </div>

      {/* Selected File */}
      <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 bg-[#1A1A1E] rounded-xl flex items-center justify-center">
            <FileText size={28} className={file ? 'text-[#32D583]' : 'text-[#6B6B70]'} />
          </div>
          <div className="flex-1">
            {file ? (
              <div>
                <p className="text-[#FAFAF9] text-base font-medium">{file.name}</p>
                <p className="text-[#6B6B70] text-sm">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
            ) : (
              <p className="text-[#6B6B70] text-base">尚未选择文件</p>
            )}
          </div>
          {file && (
            <button onClick={() => setFile(null)} className="p-2">
              <X size={20} className="text-[#6B6B70]" />
            </button>
          )}
        </div>
      </div>

      {/* Company Info */}
      <div className="bg-[#16161A] rounded-2xl p-5 border border-[#2A2A2E]">
        <h3 className="text-[#FAFAF9] text-lg font-semibold mb-4">公司信息（可选）</h3>
        <div>
          <label className="text-[#6B6B70] text-sm mb-2 block">公司名称</label>
          <input
            type="text"
            placeholder="AI将自动从报表中识别..."
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className="w-full bg-[#1A1A1E] text-[#FAFAF9] rounded-xl py-4 px-5 text-base border border-[#2A2A2E] focus:border-[#32D583] focus:outline-none placeholder:text-[#6B6B70]"
          />
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="text-[#6B6B70] text-sm mb-2 block">市场（可选）</label>
            <select
              value={market}
              onChange={(e) => setMarket(e.target.value as any)}
              className="w-full bg-[#1A1A1E] text-[#FAFAF9] rounded-xl py-4 px-5 text-base border border-[#2A2A2E] focus:border-[#32D583] focus:outline-none"
            >
              <option value="CN">CN</option>
              <option value="HK">HK</option>
              <option value="US">US</option>
            </select>
          </div>
          <div>
            <label className="text-[#6B6B70] text-sm mb-2 block">股票代码（可选）</label>
            <input
              type="text"
              placeholder="例如 AAPL / 00700 / 600519"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-[#1A1A1E] text-[#FAFAF9] rounded-xl py-4 px-5 text-base border border-[#2A2A2E] focus:border-[#32D583] focus:outline-none placeholder:text-[#6B6B70]"
            />
            <div className="text-[#6B6B70] text-xs mt-2">
              填写后可绑定公司，报告详情可显示“所属行业”。
            </div>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-[#E85A4F]/20 text-[#E85A4F] rounded-xl p-4 text-center">
          {error}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-4">
        <button 
          onClick={() => router.back()}
          className="flex-1 bg-[#1A1A1E] text-[#FAFAF9] rounded-xl py-4 px-5 font-medium text-base border border-[#2A2A2E]"
        >
          取消
        </button>
        <button 
          onClick={handleUpload}
          disabled={uploading}
          className="flex-1 bg-[#32D583] text-white rounded-xl py-4 px-5 font-semibold text-base flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {uploading ? (
            '上传中...'
          ) : (
            <>
              <Check size={22} />
              开始分析
            </>
          )}
        </button>
      </div>
    </div>
  );
}
