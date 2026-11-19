import React from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  className = '',
  id,
  ...props
}) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="w-full flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="font-mono text-[11px] uppercase tracking-[0.05em] text-[#a3afbf]">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`w-full bg-white/[0.04] border ${
          error ? 'border-[#ffb4ab] focus:border-[#ffb4ab]' : 'border-white/15 focus:border-[#7ce8f2] focus:ring-1 focus:ring-[#7ce8f2]'
        } text-white placeholder-[#93a0b2] text-[15px] px-3.5 py-2.5 rounded-[14px] h-12 transition-colors duration-150 focus:outline-none ${className}`}
        {...props}
      />
      {error && <p className="text-[13px] text-[#ffb4ab] mt-0.5">{error}</p>}
      {!error && helperText && <p className="text-xs text-[#a3afbf] mt-0.5">{helperText}</p>}
    </div>
  );
};

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Textarea: React.FC<TextareaProps> = ({
  label,
  error,
  helperText,
  className = '',
  id,
  ...props
}) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="w-full flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="font-mono text-[11px] uppercase tracking-[0.05em] text-[#a3afbf]">
          {label}
        </label>
      )}
      <textarea
        id={inputId}
        className={`w-full bg-[#0e141e] border ${
          error ? 'border-[#FFB4AB] focus:border-[#FFB4AB]' : 'border-[#243041] focus:border-[#7ce8f2]'
        } text-[#FFFFFF] placeholder-[#7a8698] text-sm p-3.5 rounded transition-colors duration-150 focus:outline-none resize-none ${className}`}
        {...props}
      />
      {error && <p className="text-[13px] text-[#ffb4ab] mt-0.5">{error}</p>}
      {!error && helperText && <p className="text-xs text-[#a3afbf] mt-0.5">{helperText}</p>}
    </div>
  );
};

