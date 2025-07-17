import React from 'react';

const Slider = ({ 
  id, 
  min, 
  max, 
  value, 
  onChange, 
  className = '' 
}) => {
  const percentage = ((value - min) / (max - min)) * 100;

  return (
    <div className={`slider-container ${className}`}>
      <div className="slider-track">
        <div 
          className="slider-progress" 
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
      <input
        type="range"
        id={id}
        min={min}
        max={max}
        value={value}
        onChange={onChange}
        className="slider-input"
      />
    </div>
  );
};

export default Slider; 