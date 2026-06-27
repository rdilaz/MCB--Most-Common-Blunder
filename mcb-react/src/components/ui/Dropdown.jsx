import React, { useState } from 'react';

const Dropdown = ({ id, value, onChange, children }) => {
  const [isOpen, setIsOpen] = useState(false);

  const handleMouseDown = () => setIsOpen(!isOpen);
  const handleBlur = () => {
    setTimeout(() => setIsOpen(false), 150);
  };

  return (
    <div className="custom-dropdown">
      <select 
        id={id}
        value={value}
        onChange={onChange}
        onMouseDown={handleMouseDown}
        onBlur={handleBlur}
      >
        {children}
      </select>
      <span className={`dropdown-triangle ${isOpen ? 'rotated' : ''}`}>▼</span>
    </div>
  );
};

export default Dropdown;
