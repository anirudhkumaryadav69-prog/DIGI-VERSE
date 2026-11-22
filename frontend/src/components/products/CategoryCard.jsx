import { Link } from 'react-router-dom';
import { ArrowUpRight, FolderTree } from 'lucide-react';

const CategoryCard = ({ category }) => {
  if (!category) return null;

  return (
    <Link
      to={`/categories/${category.slug}`}
      className="group dv-card-interactive p-6 flex flex-col justify-between focus-visible:outline-2 focus-visible:outline-[#FF6B0A]"
    >
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="w-10 h-10 rounded-xl bg-[#FFF2E6] border border-[#FFD4AE] flex items-center justify-center text-[#FF6B0A]">
            <FolderTree className="w-4 h-4" aria-hidden="true" />
          </div>
          <span className="text-xs font-mono font-medium rounded-full px-2.5 py-0.5 bg-[#FFF6ED] border border-[#E5E7EB] text-[#64748B]">
            {category.product_count} {category.product_count === 1 ? 'Product' : 'Products'}
          </span>
        </div>

        <h3 className="text-lg md:text-xl font-semibold text-[#1F2937] group-hover:text-[#FF6B0A] transition mb-2">
          {category.name}
        </h3>

        {category.description && (
          <p className="text-xs text-[#64748B] line-clamp-3 leading-relaxed">
            {category.description}
          </p>
        )}
      </div>

      <div className="pt-4 mt-5 border-t border-[#E5E7EB] flex items-center justify-between text-xs font-semibold text-[#FF6B0A]">
        <span>Explore Collection</span>
        <ArrowUpRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" aria-hidden="true" />
      </div>
    </Link>
  );
};

export default CategoryCard;
