import React from 'react';

/**
 * Reusable LoadingSpinner Component
 * 
 * Supports variants:
 * - size: 'small' | 'medium' | 'large' (also accepts 'sm' | 'md' | 'lg')
 * - text: optional status or descriptive text
 * - inline: boolean (if true, rendered inline for buttons or inline controls)
 * - color: optional Tailwind color class (defaults to indigo/purple accent)
 */
export default function LoadingSpinner({
  size = 'medium',
  text = null,
  inline = false,
  color = 'text-indigo-600 dark:text-indigo-400',
  className = '',
}) {
  // Normalize size
  const sizeKey = size === 'sm' ? 'small' : size === 'lg' ? 'large' : size === 'md' ? 'medium' : size;

  const sizeClasses = {
    small: 'w-4 h-4 border-2',
    medium: 'w-8 h-8 border-[3px]',
    large: 'w-14 h-14 border-4',
  }[sizeKey] || 'w-8 h-8 border-[3px]';

  const textClasses = {
    small: 'text-xs font-medium',
    medium: 'text-sm font-semibold',
    large: 'text-base font-bold',
  }[sizeKey] || 'text-sm font-semibold';

  // Explicit dimensions in pixels so SVG never explodes in Vanilla CSS
  const pixelDims = {
    small: { w: 18, h: 18 },
    medium: { w: 32, h: 32 },
    large: { w: 48, h: 48 },
  }[sizeKey] || { w: 32, h: 32 };

  const spinnerSvg = (
    <svg
      style={{
        width: `${pixelDims.w}px`,
        height: `${pixelDims.h}px`,
        minWidth: `${pixelDims.w}px`,
        minHeight: `${pixelDims.h}px`,
        maxWidth: `${pixelDims.w}px`,
        maxHeight: `${pixelDims.h}px`,
        color: '#6366f1',
        animation: 'spin 1s linear infinite',
      }}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3.5"
        strokeOpacity="0.25"
      />
      <path
        fill="currentColor"
        opacity="0.85"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );

  if (inline) {
    return (
      <span className={`inline-flex items-center gap-2 ${className}`}>
        {spinnerSvg}
        {text && <span className={textClasses}>{text}</span>}
      </span>
    );
  }

  return (
    <div className={`flex flex-col items-center justify-center p-4 text-center ${className}`} style={{ minHeight: '120px' }}>
      <div className="relative flex items-center justify-center">
        {spinnerSvg}
      </div>
      {text && (
        <p className="mt-3 text-slate-700 font-medium text-sm tracking-wide">
          {text}
        </p>
      )}
    </div>
  );
}
