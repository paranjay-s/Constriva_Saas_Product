import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevated?: boolean;
  interactive?: boolean;
  selected?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  elevated = false,
  interactive = false,
  selected = false,
  className = '',
  ...props
}) => {
  // the dashboard's card (dashboard.css .cv-card): a dark gradient, a hairline border, blur behind
  const bg = elevated
    ? 'bg-[linear-gradient(180deg,rgba(18,26,38,0.92),rgba(10,15,22,0.88))]'
    : 'bg-[linear-gradient(180deg,rgba(14,20,30,0.88),rgba(8,12,18,0.84))]';
  const border = selected
    ? 'border-[#7ce8f2]/60 ring-1 ring-[#7ce8f2]/60'
    : 'border-white/10 hover:border-white/20';
  const interactiveStyles = interactive
    ? 'cursor-pointer transition-all duration-150 hover:-translate-y-0.5'
    : '';

  return (
    <div
      className={`rounded-[22px] border backdrop-blur-md ${bg} ${border} ${interactiveStyles} p-5 sm:p-6 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

