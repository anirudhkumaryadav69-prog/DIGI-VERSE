import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { getCategoryTheme } from '../../utils/categoryTheme';
import { CategoryDisciplineStrip, CategoryVisualIcon } from './CategoryVisual';

const CategoryCard = ({ category }) => {
  if (!category) return null;

  const theme = getCategoryTheme(category.slug || category.name);

  return (
    <Link
      to={`/categories/${category.slug}`}
      className="group dv-card-interactive relative overflow-hidden p-6 flex flex-col justify-between bg-white rounded-2xl border border-[#D5DEE8] focus-visible:outline-2 focus-visible:outline-[#2563EB]"
    >
      <div className={`absolute inset-x-0 top-0 h-1 ${theme.accentLineClass}`} aria-hidden="true" />

      <div>
        <div className="flex items-center justify-between gap-3 mb-4 pt-1">
          <div
            className={`w-11 h-11 rounded-xl border flex items-center justify-center shrink-0 ${theme.iconBoxClass}`}
          >
            <CategoryVisualIcon theme={theme} className="w-5 h-5" />
          </div>
          <span className="text-[12px] font-medium rounded-full px-2.5 py-0.5 bg-[#EAF4FC] border border-[#D5DEE8] text-[#263445] tabular-nums">
            {category.product_count} {category.product_count === 1 ? 'product' : 'products'}
          </span>
        </div>

        <h3 className="text-[18px] leading-snug font-semibold text-[#263445] group-hover:text-[#2563EB] transition-colors mb-1.5">
          {category.name}
        </h3>

        {category.description && (
          <p className="text-[13.5px] text-[#64748B] line-clamp-2 leading-relaxed">
            {category.description}
          </p>
        )}
      </div>

      <div className="pt-4 mt-5 border-t border-[#E5E7EB] flex items-center justify-between gap-2 text-[13px] font-semibold text-[#263445] group-hover:text-[#2563EB] transition-colors">
        <div className="flex items-center gap-2 min-w-0">
          <CategoryDisciplineStrip icons={theme.disciplineIcons} className="w-3.5 h-3.5" />
          <span className="truncate">{theme.disciplineLabel || 'Explore collection'}</span>
        </div>
        <ArrowUpRight
          className="w-4 h-4 shrink-0 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
          aria-hidden="true"
        />
      </div>
    </Link>
  );
};

export default CategoryCard;
