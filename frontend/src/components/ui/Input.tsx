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
        <label htmlFor={inputId} className="text-xs uppercase tracking-wider font-semibold text-[#A6A6A6]">
          {label}
        </label>
      )}
      <input
        id={inputId}
        className={`w-full bg-[#181818] border ${
          error ? 'border-[#FFB4AB] focus:border-[#FFB4AB]' : 'border-[#303030] focus:border-[#C5A77B]'
        } text-[#FFFFFF] placeholder-[#666666] text-sm px-3.5 py-2.5 rounded h-11 transition-colors duration-150 focus:outline-none ${className}`}
        {...props}
      />
      {error && <p className="text-xs text-[#FFB4AB] mt-0.5">{error}</p>}
      {!error && helperText && <p className="text-xs text-[#737373] mt-0.5">{helperText}</p>}
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
        <label htmlFor={inputId} className="text-xs uppercase tracking-wider font-semibold text-[#A6A6A6]">
          {label}
        </label>
      )}
      <textarea
        id={inputId}
        className={`w-full bg-[#181818] border ${
          error ? 'border-[#FFB4AB] focus:border-[#FFB4AB]' : 'border-[#303030] focus:border-[#C5A77B]'
        } text-[#FFFFFF] placeholder-[#666666] text-sm p-3.5 rounded transition-colors duration-150 focus:outline-none resize-none ${className}`}
        {...props}
      />
      {error && <p className="text-xs text-[#FFB4AB] mt-0.5">{error}</p>}
      {!error && helperText && <p className="text-xs text-[#737373] mt-0.5">{helperText}</p>}
    </div>
  );
};

