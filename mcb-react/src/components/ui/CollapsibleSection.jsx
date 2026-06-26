import React, { useState } from 'react';

const CollapsibleSection = ({
  title,
  containerClassName,
  headerClassName,
  contentClassName,
  children
}) => {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className={containerClassName}>
      <div className={headerClassName} onClick={() => setIsExpanded(!isExpanded)}>
        {title}
        <span className={`toggle-icon ${isExpanded ? 'rotated' : ''}`}>▼</span>
      </div>
      <div className={`${contentClassName} ${isExpanded ? '' : 'collapsed'}`}>
        {children}
      </div>
    </div>
  );
};

export default CollapsibleSection;
